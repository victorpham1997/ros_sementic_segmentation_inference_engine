#!/usr/bin/env python

import time
import rospy
import json
import os

from std_msgs.msg import Int32
from std_msgs.msg import String
from cv_bridge import CvBridge, CvBridgeError
from sensor_msgs.msg import Image

import numpy as np
from keras import backend as K
from keras.utils import multi_gpu_model
from keras.models import load_model
import tensorflow as tf
import cv2

from utils import apply_color_map
import model

# Name of the weights and config json file
weights = "/weights4.h5"
config_json = "/config.json"
path = os.path.dirname(os.path.abspath(__file__))


class seg_node:
	def __init__(self):
		# Workaround to forbid tensorflow from crashing the gpu
		config = tf.ConfigProto()
		config.gpu_options.allow_growth = True
		self.sess = tf.Session(config=config)
		K.set_session(self.sess)

		self.weights = path + weights
		self.net = model.build_bn(480, 320, 3, train=True)
		self.net.load_weights(self.weights, by_name=True)
		self.img_height = self.net.inputs[0].shape[2]
		self.img_width = self.net.inputs[0].shape[1]

		# Publisher
		self.seg_img_publisher = rospy.Publisher("seg_img",Image)
		# sensor_msgs/Image to cv_img
		self.bridge = CvBridge() 
		# Subscriber
		self.img_subscriber = rospy.Subscriber("/pointgrey_cam/image_rect_color", Image, self.inference_callback)


	def inference_callback(self, data):
		# convert sensor_msgs Image to cv2 data
		try:
			cv_img = self.bridge.imgmsg_to_cv2(data, "bgr8")
		except CvBridgeError as e:
			print(e)

		# Inferencing
		with self.sess.as_default():    #this is to ensure the same session and graph is used for all inferences
			with self.sess.graph.as_default():
				print("Inference engine running")
				x = np.array([cv2.resize(cv_img,(self.img_height, self.img_width))])
				y = self.net.predict(np.array(x), batch_size=1)

		# Applying colour map based on config.json
		with open(path + config_json) as config_file:
		    config = json.load(config_file)
		labels = config['labels']
		output = apply_color_map(np.argmax(y[0], axis=-1), labels)
		mask = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)

		# layering the mask on top of original image
		overlay = cv2.resize(mask, (480, 320))
		output = x[0]
		alpha = 0.5 #opacity ratio
		cv2.addWeighted(overlay, alpha, output, 1 - alpha,0, output)

		# convert cv2 data to sensor_msgs Image to publish
		try:
			output = self.bridge.cv2_to_imgmsg(output, "bgr8")
			self.seg_img_publisher.publish(output)
		except CvBridgeError as e:
			print(e)



def main():
	rospy.init_node("seg_inference_engine", anonymous=True)
	node = seg_node()
	try:
		rospy.spin()
	except KeyboardInterrupt:
		print("Shutting down")

if __name__ == '__main__':
	main()
	
	





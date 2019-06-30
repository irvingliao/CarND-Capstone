from styx_msgs.msg import TrafficLight

import rospy
import rospkg
import os,sys
import tensorflow as tf
import numpy as np
import time
import cv2

class TLClassifier(object):
    def __init__(self, is_site=False):
        # load classifier
        self.sess = None
        self.predict = None
		
        rospy.loginfo('tl_classifier start')
		
        current_path = rospkg.RosPack().get_path('tl_detector')

        if is_site:
           self.model_path = current_path + '/light_classification/models/real_mobilenets_ssd_38k_epochs_frozen_inference_graph.pb'
        else:
           self.model_path = current_path + '/light_classification/models/sim_mobilenets_ssd_30k_epochs_frozen_inference_graph.pb'

        rospy.loginfo('Loading model: ' + self.model_path)

        # Load graph from model
        self.detection_graph = self.load_graph(self.model_path)

        self.config = tf.ConfigProto()
        self.config.gpu_options.allow_growth = True

        # The input placeholder for the image.
        # `get_tensor_by_name` returns the Tensor with the associated name in the Graph.
        self.image_tensor = self.detection_graph.get_tensor_by_name('image_tensor:0')

        # Each score represent how level of confidence for each of the objects.
        # Score is shown on the result image, together with the class label.
        self.detection_scores = self.detection_graph.get_tensor_by_name('detection_scores:0')

        # The classification of the object (integer id).
        self.detection_classes = self.detection_graph.get_tensor_by_name('detection_classes:0')

        # Number of predictions found in the image
        self.num_detections = self.detection_graph.get_tensor_by_name('num_detections:0')

        with self.detection_graph.as_default():
            self.sess = tf.Session(graph=self.detection_graph, config=self.config)

    def load_graph(self, graph_file):
        """Loads a frozen inference graph"""
        graph = tf.Graph()
        with graph.as_default():
            od_graph_def = tf.GraphDef()
            with tf.gfile.GFile(graph_file, 'rb') as fid:
                serialized_graph = fid.read()
                od_graph_def.ParseFromString(serialized_graph)
                tf.import_graph_def(od_graph_def, name='')
        return graph

    def filter_obj(self, min_score, scores, classes):
        """Return boxes with a confidence >= `min_score`"""
        n = len(classes)
        idxs = []
        for i in range(n):
            if scores[i] >= min_score:
                idxs.append(i)
        
        filtered_scores = scores[idxs, ...]
        filtered_classes = classes[idxs, ...]
        return filtered_scores, filtered_classes

    def get_classification(self, image, confidence_cutoff=0.3):
        """Determines the color of the traffic light in the image

        Args:
            image (cv::Mat): image containing the traffic light

        Returns:
            int: ID of traffic light color (specified in styx_msgs/TrafficLight)

        """
        # implement light color prediction
        image_np = np.expand_dims(np.asarray(image, dtype=np.uint8), 0)

        (scores, classes, num) = self.sess.run([self.detection_scores,
                                                self.detection_classes, 
                                                self.num_detections], 
                                                feed_dict={self.image_tensor: image_np})

        scores = np.squeeze(scores)
        classes = np.squeeze(classes).astype(np.int32)

        output_score, output_classes = self.filter_obj(confidence_cutoff, scores, classes)

        lights = ["red", "yellow", "green"]

        if len(output_classes) == 0:            
            rospy.loginfo("tl_classifier.py: Predicted light Unknown")
            return TrafficLight.UNKNOWN
        else:
            colorIndex = output_classes[0] - 1
        rospy.loginfo("tl_classifier.py: Predicted light: " + lights[colorIndex] + " , score: " + str(output_score[0]))

        if colorIndex == 0:
            return TrafficLight.RED
        elif colorIndex == 1:
            return TrafficLight.YELLOW
        elif colorIndex == 2:
            return TrafficLight.GREEN
        else:
            return TrafficLight.UNKNOWN

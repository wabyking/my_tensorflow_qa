#!/usr/bin/env python
#encoding=utf-8

import tensorflow as tf
import numpy as np

class QA_overlap(object):
    def __init__(
      self, max_len_left, max_len_right, vocab_size,
      embedding_size,embeddings,filter_sizes, num_filters, num_hidden, 
      l2_reg_lambda=0.0,is_Embedding_Needed = False):

        # Placeholders for input, output and dropout
        self.input_left = tf.placeholder(tf.int32, [None, max_len_left], name="input_left")
        self.input_right = tf.placeholder(tf.int32, [None, max_len_right], name="input_right")
        self.input_y = tf.placeholder(tf.float32, [None,2], name = "input_y")
        self.overlap = tf.placeholder(tf.float32,[None,2],name = 'overlap')
        self.dropout_keep_prob = tf.placeholder(tf.float32, name = "dropout_keep_prob")

        # Embedding layer for both CNN
        with tf.device('/cpu:0'), tf.name_scope("embedding"):
            if is_Embedding_Needed:
            # W = tf.Variable(
            #     tf.random_uniform([vocab_size, embedding_size], -1.0, 1.0),
            #     name="W")
                W = tf.Variable(np.array(embeddings),name="W" ,dtype="float32",trainable = True)
            else:
                W = tf.Variable(
                tf.random_uniform([vocab_size, embedding_size], -1.0, 1.0),
                name="W")
            self.embedded_chars_left = tf.expand_dims(tf.nn.embedding_lookup(W, self.input_left), -1)
            self.embedded_chars_right = tf.expand_dims(tf.nn.embedding_lookup(W, self.input_right), -1)

        # Create a convolution + maxpool layer for each filter size
        pooled_outputs_left = []
        pooled_outputs_right = []
        for i, filter_size in enumerate(filter_sizes):
            filter_shape = [filter_size, embedding_size, 1, num_filters]
            with tf.name_scope("conv-maxpool-left-%s" % filter_size):
                # Convolution Layer
                W = tf.Variable(tf.truncated_normal(filter_shape, stddev=0.1), name="W")
                b = tf.Variable(tf.constant(0.1, shape=[num_filters]), name="b")
                conv = tf.nn.conv2d(
                    self.embedded_chars_left,
                    W,
                    strides=[1, 1, 1, 1],
                    padding="VALID",
                    name="conv")
                # Apply nonlinearity
                h = tf.nn.relu(tf.nn.bias_add(conv, b), name="relu")
                # Maxpooling over the outputs
                pooled = tf.nn.max_pool(
                    h,
                    ksize=[1, max_len_left - filter_size + 1, 1, 1],
                    strides=[1, 1, 1, 1],
                    padding='VALID',
                    name="pool")
                pooled_outputs_left.append(pooled)
            with tf.name_scope("conv-maxpool-right-%s" % filter_size):
                # Convolution Layer
                # W = tf.Variable(tf.truncated_normal(filter_shape, stddev=0.1), name="W")
                # b = tf.Variable(tf.constant(0.1, shape=[num_filters]), name="b")
                conv = tf.nn.conv2d(
                    self.embedded_chars_right,
                    W,
                    strides=[1, 1, 1, 1],
                    padding="VALID",
                    name="conv")
                # Apply nonlinearity
                h = tf.nn.relu(tf.nn.bias_add(conv, b), name="relu")
                # Maxpooling over the outputs
                pooled = tf.nn.max_pool(
                    h,
                    ksize=[1, max_len_right - filter_size + 1, 1, 1],
                    strides=[1, 1, 1, 1],
                    padding='VALID',
                    name="pool")
                pooled_outputs_right.append(pooled)

        # Combine all the pooled features
        num_filters_total = num_filters * len(filter_sizes)
        self.h_pool_left = tf.reshape(tf.concat(3, pooled_outputs_left), [-1, num_filters_total], name='h_pool_left')
        self.h_pool_right = tf.reshape(tf.concat(3, pooled_outputs_right), [-1, num_filters_total], name='h_pool_right')
        print self.h_pool_left
        print self.h_pool_right

        # Compute similarity
        with tf.name_scope("similarity"):
            W = tf.get_variable(
                "W",
                shape=[num_filters_total, num_filters_total],
                initializer=tf.contrib.layers.xavier_initializer())
            self.transform_left = tf.matmul(self.h_pool_left, W)
            self.sims = tf.reduce_sum(tf.mul(self.transform_left, self.h_pool_right), 1, keep_dims=True)
            print self.sims

        # Keeping track of l2 regularization loss (optional)
        l2_loss = tf.constant(0.0)

        # Make input for classification
        self.new_input = tf.concat(1, [self.h_pool_left, self.sims, self.h_pool_right], name='new_input')

        
        # # make a softmax regression
        # W = tf.Variable(tf.random_uniform([2 * num_filters_total + 1,1]), name="W")
        # b = tf.Variable(tf.constant(0.1), name="b")
        # # Construct model
        # self.predictions = tf.sigmoid(tf.nn.l2_normalize(tf.matmul(self.new_input, W) + b,dim = 0),name = 'predictions') # Softmax
        # self.scores = self.predictions
        # # Minimize error using cross entropy
        # self.loss = tf.reduce_mean(-tf.reduce_sum(self.input_y * tf.log(self.predictions),reduction_indices = 1))
        # self.accuracy = 1 - self.loss
        
        # # Add dropout
        # with tf.name_scope("dropout"):
        #     self.h_drop = tf.nn.dropout(self.new_input, self.dropout_keep_prob)
        # # Final (unnormalized) scores and predictions
        # with tf.name_scope("output"):
        #     W = tf.get_variable(
        #         "W_regression",
        #         shape=[2*num_filters_total+1, 1],
        #         initializer=tf.contrib.layers.xavier_initializer())
        #     b = tf.Variable(tf.constant(0.1,shape = [1]), name="b")
        #     l2_loss += tf.nn.l2_loss(W)
        #     l2_loss += tf.nn.l2_loss(b)

        #     self.scores =  tf.reshape ( tf.nn.xw_plus_b(self.new_input, W, b, name="scores"),[-1])
        #     self.predictions =  tf.reshape (tf.sigmoid(self.scores, name="predictions"),[-1])

        # # CalculateMean cross-entropy loss
        # with tf.name_scope("loss"):
        #     losses = tf.nn.softmax_cross_entropy_with_logits(logits=self.scores+0.001, labels=self.input_y+0.001)
        #     self.loss = tf.reduce_sum(losses) + l2_reg_lambda * l2_loss

        # # Accuracy
        # with tf.name_scope("accuracy"):
        #     correct_predictions = tf.equal(self.predictions, self.input_y)
        #     self.accuracy = tf.reduce_mean(tf.cast(correct_predictions, "float"), name="accuracy")
        
        # hidden layer
        # with tf.name_scope("hidden"):
        #     W = tf.get_variable(
        #         "W_hidden",
        #         shape=[2*num_filters_total+1, num_hidden],
        #         initializer=tf.contrib.layers.xavier_initializer())
        #     b = tf.Variable(tf.constant(0.1, shape=[num_hidden]), name="b")
        #     l2_loss += tf.nn.l2_loss(W)
        #     l2_loss += tf.nn.l2_loss(b)
        #     self.hidden_output = tf.nn.relu(tf.nn.xw_plus_b(self.new_input, W, b, name="hidden_output"))

        # # Add dropout
        # with tf.name_scope("dropout"):
        #     self.h_drop = tf.nn.dropout(self.hidden_output, self.dropout_keep_prob, name="hidden_output_drop")
        #     print self.h_drop

        # Final (unnormalized) scores and predictions


        with tf.name_scope('dropout'):
            self.h_drop = tf.nn.dropout(self.new_input, self.dropout_keep_prob,name = 'drop_out')

        self.new_input_overlap = tf.concat(1,[self.h_drop,self.overlap],name = 'new_input_overlap')
        with tf.name_scope("output"):
            W = tf.get_variable(
                "W_output",
                shape=[2 * num_filters_total + 1 + 2, 2],
                initializer=tf.contrib.layers.xavier_initializer())
            b = tf.Variable(tf.constant(0.1, shape=[2]), name="b")
            l2_loss += tf.nn.l2_loss(W)
            l2_loss += tf.nn.l2_loss(b)
            self.scores = tf.nn.softmax(tf.nn.xw_plus_b(self.new_input_overlap, W, b, name="scores"))
            self.predictions = tf.argmax(self.scores, 1, name="predictions")

        # CalculateMean cross-entropy loss
        with tf.name_scope("loss"):
            # losses = tf.nn.softmax_cross_entropy_with_logits(self.scores, self.input_y)
            losses = -tf.reduce_sum(self.input_y * tf.log(self.scores),reduction_indices = 1)
            self.loss = tf.reduce_mean(losses) + l2_reg_lambda * l2_loss

        # Accuracy
        with tf.name_scope("accuracy"):
            correct_predictions = tf.equal(self.predictions, tf.argmax(self.input_y, 1))
            self.accuracy = tf.reduce_mean(tf.cast(correct_predictions, "float"), name="accuracy")
       

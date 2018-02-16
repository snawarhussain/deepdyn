import os
from itertools import count

import cv2
import numpy as np
from PIL import Image as IMG

import preprocess.algorithms.fast_mst as fmst
import preprocess.utils.img_utils as imgutils
from commons.IMAGE import Image
from commons.MAT import Mat
from commons.accumulator import Accumulator


class AtureTest:
    def __init__(self, data_dir=None, log_dir=None):

        self.data_dir = data_dir
        self.log_dir = log_dir

        if os.path.isdir(self.log_dir) is False:
            os.makedirs(self.log_dir)
            self.log_file = open(self.log_dir + os.sep + "segmentation_result.csv", 'w')
        else:
            self.log_file = open(self.log_dir + os.sep + "segmentation_result.csv", 'w')

        self.log_file.write(
            'ITERATION,EPOCH,FILE_NAME,FSCORE,PRECISION,RECALL,ACCURACY,' \
            'SKELETONIZE_THRESHOLD,' \
            'IMG_LATTICE_COST_ASSIGNMENT_ALPHA,' \
            'IMG_LATTICE_COST_GABOR_IMAGE_CONTRIBUTION,' \
            'SEGMENTATION_THRESHOLD\n'
        )

        self.mask_dir = None
        self.ground_truth_dir = None
        self.fget_mask_file = None
        self.fget_ground_truth_file = None
        self.erode_mask = None
        self.c = count(1)

    def load_mask(self, mask_dir=None, fget_mask_file=None, erode_mask=False):
        self.mask_dir = mask_dir
        self.fget_mask_file = fget_mask_file
        self.erode_mask = erode_mask

    def load_ground_truth(self, ground_truth_dir=None, fget_ground_truth_file=None):
        self.ground_truth_dir = ground_truth_dir
        self.fget_ground_truth_file = fget_ground_truth_file

    def _segment_now(self, accumulator=None, params={}):
        accumulator.img_obj.create_skeleton(threshold=params['sk_threshold'],
                                            kernels=imgutils.get_chosen_skeleton_filter())
        seed_node_list = imgutils.get_seed_node_list(accumulator.img_obj.img_skeleton)

        fmst.run_segmentation(accumulator=accumulator,
                              seed_list=seed_node_list,
                              segmentation_threshold=params['seg_threshold'],
                              alpha=params['alpha'],
                              img_gabor_contribution=params['gabor_contrib'],
                              img_original_contribution=1.0 - params['gabor_contrib'])

    def _load_file(self, file_name=None):
        img = IMG.open(os.path.join(self.data_dir, file_name))
        orig = np.array(img.getdata(), np.uint8).reshape(img.size[1], img.size[0], 3)
        print('\nFile loaded: ' + file_name)
        return orig

    def _load_mask(self, img_object=None):
        mask_file = self.fget_mask_file(img_object.file_name)

        try:
            mask = IMG.open(os.path.join(self.mask_dir, mask_file))
            mask = np.array(mask.getdata(), np.uint8).reshape(mask.size[1], mask.size[0], 1)[:, :, 0]

            if self.erode_mask:
                kern = np.array([
                    [0.0, 0.0, 0.5, 0.0, 0.0],
                    [0.0, 0.2, 1.0, 0.2, 0.0],
                    [0.5, 1.0, 1.5, 1.0, 0.5],
                    [0.0, 0.2, 1.0, 0.2, 0.0],
                    [0.0, 0.0, 0.5, 0.0, 0.0],
                ], np.uint8)

                print('Mask loaded: ' + mask_file)
                return cv2.erode(mask, kern, iterations=5)
        except:
            print('!!! Mask not found')
            return np.zeros_like(img_object.img_array)

    def _load_ground_truth(self, file_name=None):

        try:
            gt_file = self.fget_ground_truth_file(file_name)
            truth = IMG.open(os.path.join(self.ground_truth_dir, gt_file))
            truth = np.array(truth.getdata(), np.uint8).reshape(truth.size[1], truth.size[0], 1)[:, :, 0]
            print('Ground truth loaded: ' + gt_file)
            return truth
        except:
            print('!!! Ground truth not found')
            return None

    def _initialize_image(self, file_name=None):

        rgb = self._load_file(file_name=file_name)
        img_obj = Image(image_arr=rgb[:, :, 1], file_name=file_name)

        mask = self._load_mask(img_object=img_obj)
        truth = self._load_ground_truth(file_name=file_name)

        img_obj.img_array = cv2.bitwise_and(img_obj.img_array, img_obj.img_array, mask=mask)

        img_obj.generate_lattice_graph()
        print('Lattice created')

        return Accumulator(img_obj=img_obj, mask=mask, ground_truth=truth)

    def precision_recall_accuracy(self, accumulator=None):

        if accumulator.ground_truth is None:
            accumulator.rgb_accumulator[:, :, 0] = accumulator.accumulator
            accumulator.rgb_accumulator[:, :, 1] = accumulator.accumulator
            accumulator.rgb_accumulator[:, :, 2] = accumulator.accumulator
            return 0.01, 0.01, 0.01

        TP = 0  # True Positive
        FP = 0  # False Positive
        FN = 0  # False Negative
        TN = 0  # True Negative
        for i in range(0, accumulator.accumulator.shape[0]):
            for j in range(0, accumulator.accumulator.shape[1]):

                if accumulator.accumulator[i, j] == 255:
                    accumulator.rgb_accumulator[i, j, 0] = 255
                    accumulator.rgb_accumulator[i, j, 1] = 255
                    accumulator.rgb_accumulator[i, j, 2] = 255

                if accumulator.accumulator[i, j] == 255 and accumulator.ground_truth[i, j] == 255:
                    TP += 1
                if accumulator.accumulator[i, j] == 255 and accumulator.ground_truth[i, j] == 0:
                    accumulator.rgb_accumulator[i, j, 0] = 0
                    accumulator.rgb_accumulator[i, j, 1] = 255
                    accumulator.rgb_accumulator[i, j, 2] = 0
                    FP += 1
                if accumulator.accumulator[i, j] == 0 and accumulator.ground_truth[i, j] == 255:
                    accumulator.rgb_accumulator[i, j, 0] = 255
                    accumulator.rgb_accumulator[i, j, 1] = 0
                    accumulator.rgb_accumulator[i, j, 2] = 0
                    FN += 1
                if accumulator.accumulator[i, j] == 0 and accumulator.ground_truth[i, j] == 0:
                    TN += 1

        return TP / (TP + FP), TP / (TP + FN), (TP + TN) / (TP + FP + FN + TN)

    def _run(self, accumulator=None, params_combination=[],
             save_images=False, log=False, epoch=0):

        accumulator.img_obj.apply_bilateral()
        accumulator.img_obj.apply_gabor(kernel_bank=imgutils.get_chosen_gabor_bank())
        print('Filter applied')

        self.c = count(1)

        for params in params_combination:
            self._segment_now(accumulator=accumulator, params=params)

            accumulator.accumulator = cv2.bitwise_and(accumulator.accumulator, accumulator.accumulator,
                                                      mask=accumulator.mask)

            self._save(measures=self.precision_recall_accuracy(accumulator=accumulator),
                       accumulator=accumulator, epoch=epoch,
                       params=params,
                       log=log,
                       save_images=save_images)

    def run_for_all_images(self, params_combination=[], save_images=False, epochs=1):
        for file_name in os.listdir(self.data_dir):
            accumulator = self._initialize_image(file_name)
            self._run(accumulator=accumulator, params_combination=params_combination, save_images=save_images,
                      log=True)
        self.log_file.close()

    def run_for_one_image(self, file_name=None, params={}, save_images=False, epochs=1, alpha_decay=0.2):

        accumulator = self._initialize_image(file_name)

        for i in range(epochs):
            if i > 0:
                self._mask_segmented_vessels(accumulator=accumulator, params=params, alpha_decay=alpha_decay)
            print('Running epoch: ' + str(i))
            self._run(accumulator=accumulator,
                      params_combination=[params], save_images=save_images,
                      log=False, epoch=i)

        self.log_file.close()
        return accumulator

    def _save(self, measures=None, accumulator=None, epoch=None, params=None, log=False,
              save_images=False):

        precision, recall, accuracy = measures
        f1_score = 2 * precision * recall / (precision + recall)

        accumulator.res['image' + str(epoch)] = accumulator.img_obj.img_array.copy()
        accumulator.res['gabor' + str(epoch)] = accumulator.img_obj.img_gabor.copy()
        accumulator.res['segmented' + str(epoch)] = accumulator.accumulator.copy()
        accumulator.res['bilateral' + str(epoch)] = accumulator.img_obj.diff_bilateral.copy()
        accumulator.res['skeleton' + str(epoch)] = accumulator.img_obj.img_skeleton.copy()
        accumulator.res['params' + str(epoch)] = params
        accumulator.res['F' + str(epoch)] = f1_score
        accumulator.res['precision' + str(epoch)] = precision
        accumulator.res['recall' + str(epoch)] = recall
        accumulator.res['accuracy' + str(epoch)] = accuracy
        accumulator.accumulator = np.maximum(accumulator.res['segmented' + str(epoch)], accumulator.accumulator)
        self._save_images(accumulator=accumulator, params=params, epoch=epoch, log=log, save_images=save_images)

    def _mask_segmented_vessels(self, accumulator=None, params=None, alpha_decay=None):

        for i in range(accumulator.img_obj.img_array.shape[0]):
            for j in range(accumulator.img_obj.img_array.shape[1]):
                if accumulator.accumulator[i, j] == 255:
                    accumulator.img_obj.img_array[i, j] = 200

        params['alpha'] -= alpha_decay

    def _save_images(self, accumulator=None, params=None, epoch=None, log=False, save_images=False):
        i = next(self.c)
        line = str(i) + ',' + \
               'EP' + str(epoch) + ',' + \
               str(accumulator.img_obj.file_name) + ',' + \
               str(round(accumulator.res['F' + str(epoch)], 3)) + ',' + \
               str(round(accumulator.res['precision' + str(epoch)], 3)) + ',' + \
               str(round(accumulator.res['recall' + str(epoch)], 3)) + ',' + \
               str(round(accumulator.res['accuracy' + str(epoch)], 3)) + ',' + \
               str(round(params['sk_threshold'], 3)) + ',' + \
               str(round(params['alpha'], 3)) + ',' + \
               str(round(params['gabor_contrib'], 3)) + ',' + \
               str(round(params['seg_threshold'], 3))
        if log:
            self.log_file.write(line + '\n')
            self.log_file.flush()
        if i % 5 == 0:
            print('Number of params combination tried: ' + str(self.c))

        if save_images:
            IMG.fromarray(accumulator.rgb_accumulator).save(
                os.path.join(self.log_dir, accumulator.img_obj.file_name + '_[' + line + ']' + '.JPEG'))
            IMG.fromarray(accumulator.img_obj.img_gabor).save(
                os.path.join(self.log_dir, accumulator.img_obj.file_name + '_[' + line + ']GABOR' + '.JPEG'))
            IMG.fromarray(accumulator.img_obj.img_array).save(
                os.path.join(self.log_dir, accumulator.img_obj.file_name + '_[' + line + ']ORIG' + '.JPEG'))


class AtureTestMat(AtureTest):
    def __init__(self, data_dir=None, log_dir=None):
        super().__init__(data_dir=data_dir, log_dir=log_dir)

    def _load_file(self, file_name=None):
        file = Mat(mat_file=os.path.join(self.data_dir, file_name))
        orig = file.get_image('I2')
        print('File loaded: ' + file_name)
        return orig

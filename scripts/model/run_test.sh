#!/bin/bash
# Copyright 2019 Xilinx Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#test float model
python yolov3_test.py --batch-size 32 -pretrained ./build/float_model/yolo_base_0.pth --ratio 0

#python yolov3_test.py --batch-size 32 -pretrained ./build/float_model/yolo_base_30.pth --ratio 30

#python yolov3_test.py --batch-size 32 -pretrained ./build/float_model/yolo_base_50.pth --ratio 50

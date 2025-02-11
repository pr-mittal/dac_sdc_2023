
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

echo "Conducting test..."

export CUDA_VISIBLE_DEVICES=0
GPU_NUM=1
BATCH=4
WEIGHTS=${PWD}/float/yolox.pth
CFG=code/exps/default/yolox_s_deploy.py
# python code/tools/train.py -f ${CFG} -d ${GPU_NUM} -b 64 -o # --fp16
python code/tools/train.py -f ${CFG} -b ${BATCH} -o --resume --ckpt ${WEIGHTS} --fp16
# python -m yolox.tools.train -f ${CFG} -d ${GPU_NUM} -b ${BATCH} -o
# python -m yolox.tools.train -f ${CFG} -b ${BATCH} -o

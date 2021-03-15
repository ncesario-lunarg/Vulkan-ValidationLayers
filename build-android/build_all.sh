#!/bin/bash

# Copyright 2017 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

if [ -z "${ANDROID_SDK_HOME}" ];
then echo "Please set ANDROID_SDK_HOME, exiting"; exit 1;
else echo "ANDROID_SDK_HOME is ${ANDROID_SDK_HOME}";
fi

if [ -z "${ANDROID_NDK_HOME}" ];
then echo "Please set ANDROID_NDK_HOME, exiting"; exit 1;
else echo "ANDROID_NDK_HOME is ${ANDROID_NDK_HOME}";
fi

if [ -z "${ANDROID_PLATFORM}" ]; then
    ANDROID_PLATFORM=26
fi
echo "Using Android platform $ANDROID_PLATFORM"

if [ -z "${ANDROID_BUILD_TOOLS}" ]; then
    ANDROID_BUILD_TOOLS=$(ls -t $ANDROID_SDK_HOME/build-tools | head -1)
fi
echo "Using Android build tools version = $ANDROID_BUILD_TOOLS"

if [ -z "${ANDROID_ABI}" ]; then
    ANDROID_ABI='armeabi-v7a arm64-v8a x86 x86_64'
fi
echo "Building Android platforms $ANDROID_ABI"

if [ -z "${ANDROID_TOOLCHAIN}" ]; then
    ANDROID_TOOLCHAIN=clang
fi
echo "Using Android toolchain $ANDROID_TOOLCHAIN"

if [[ $(uname) == "Linux" ]]; then
    cores=$(nproc) || echo 4
elif [[ $(uname) == "Darwin" ]]; then
    cores=$(sysctl -n hw.ncpu) || echo 4
fi

function findtool() {
    if [[ ! $(type -t $1) ]]; then
        echo Command $1 not found, see ../BUILD.md;
        exit 1;
    fi
}

cat >$script_dir/jni/Application.mk <<EOF
# Copyright 2015 The Android Open Source Project
# Copyright (C) 2015 Valve Corporation

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#      http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

APP_ABI := $ANDROID_ABI
APP_PLATFORM := android-$ANDROID_PLATFORM
APP_STL := c++_static
NDK_TOOLCHAIN_VERSION := $ANDROID_TOOLCHAIN
NDK_MODULE_PATH := .
EOF
echo "Wrote to $script_dir/jni/Application.mk"

# Check for dependencies
aapt=$ANDROID_SDK_HOME/build-tools/$ANDROID_BUILD_TOOLS/aapt
zipalign=$ANDROID_SDK_HOME/build-tools/$ANDROID_BUILD_TOOLS/zipalign
findtool jarsigner

set -ev

LAYER_BUILD_DIR=$PWD
DEMO_BUILD_DIR=$PWD/../demos/android
echo LAYER_BUILD_DIR="${LAYER_BUILD_DIR}"
echo DEMO_BUILD_DIR="${DEMO_BUILD_DIR}"

function create_APK() {
    $aapt package -f -M AndroidManifest.xml -I "$ANDROID_SDK_HOME/platforms/android-$ANDROID_PLATFORM/android.jar" -S res -F bin/$1-unaligned.apk bin/libs
    # update this logic to detect if key is already there.  If so, use it, otherwise create it.
    jarsigner -verbose -keystore ~/.android/debug.keystore -storepass android -keypass android  bin/$1-unaligned.apk androiddebugkey
    $zipalign -f 4 bin/$1-unaligned.apk bin/$1.apk
}

#
# build layers
#
./update_external_sources_android.sh --no-build
$ANDROID_NDK_HOME/ndk-build -j $cores

#
# build VulkanLayerValidationTests APK
#
mkdir -p bin/libs/lib
cp -r $LAYER_BUILD_DIR/libs/* $LAYER_BUILD_DIR/bin/libs/lib/
create_APK VulkanLayerValidationTests

echo Builds succeeded
exit 0

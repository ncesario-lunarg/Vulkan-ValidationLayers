#!/usr/bin/python3 -i
#
# Copyright (c) 2015-2017, 2019-2021 The Khronos Group Inc.
# Copyright (c) 2015-2017, 2019-2021 Valve Corporation
# Copyright (c) 2015-2017, 2019-2021 LunarG, Inc.
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
#
# Author: Mark Lobodzinski <mark@lunarg.com>

import os
import sys
import subprocess
import platform
import shutil
import argparse

import utils.utils as utils

if sys.version_info[0] != 3:
    print("This script requires Python 3. Run script with [-h] option for more details.")
    sys_exit(0)

# helper to define paths relative to the repo root
def RepoRelative(path):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', path))

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.split(os.path.abspath(__file__))[0], '..'))

# TODO: Pass this in as arg, may be useful for running locally
EXTERNAL_DIR_NAME = "external"
BUILD_DIR_NAME = "build"
EXTERNAL_DIR = RepoRelative(EXTERNAL_DIR_NAME)
VVL_BUILD_DIR = RepoRelative(BUILD_DIR_NAME)
CONFIGURATIONS = ['release', 'debug']
DEFAULT_CONFIGURATION = CONFIGURATIONS[0]
ARCHS = [ 'x64', 'Win32' ]
DEFAULT_ARCH = ARCHS[0]

# Runs a command in a directory and returns its return code.
# Directory is project root by default, or a relative path from project root
def RunShellCmd(command, start_dir = PROJECT_ROOT, verbose=True):
    if start_dir != PROJECT_ROOT:
        start_dir = RepoRelative(start_dir)
    cmd_list = command.split(" ")
    if verbose: print(f'CICMD({cmd_list})')
    subprocess.check_call(cmd_list, cwd=start_dir)

#
# Check if the system is Windows
def IsWindows(): return 'windows' == platform.system().lower()

#
# Verify consistency of generated source code
def CheckVVLCodegenConsistency():
    print("Check Generated Source Code Consistency")
    gen_check_cmd = 'python3 scripts/generate_source.py --verify %s/Vulkan-Headers/registry' % EXTERNAL_DIR
    RunShellCmd(gen_check_cmd)

#
# Prepare the Validation Layers for testing
def BuildVVL(args):

    print("Log CMake version")
    cmake_ver_cmd = 'cmake --version'
    RunShellCmd(cmake_ver_cmd)

    print("Run update_deps.py for VVL Repository")
    update_cmd = f'python3 scripts/update_deps.py --dir {EXTERNAL_DIR_NAME} --config {args.configuration} --arch {args.arch}'
    RunShellCmd(update_cmd)

    GTEST_DIR = RepoRelative("external/googletest")
    if not os.path.exists(GTEST_DIR):
        print("Clone Testing Framework Source Code")
        clone_gtest_cmd = f'git clone https://github.com/google/googletest.git {GTEST_DIR}'
        RunShellCmd(clone_gtest_cmd)

        print("Get Specified Testing Source")
        gtest_checkout_cmd = 'git checkout tags/release-1.8.1'
        RunShellCmd(gtest_checkout_cmd, GTEST_DIR)

    utils.make_or_exist_dirs(VVL_BUILD_DIR)
    print("Run CMake for Validation Layers")
    cmake_cmd = f'cmake -C ../{EXTERNAL_DIR_NAME}/helper.cmake -DCMAKE_BUILD_TYPE={args.configuration.capitalize()} ..'
    if IsWindows(): cmake_cmd = cmake_cmd + f' -A {args.arch}'
    RunShellCmd(cmake_cmd, VVL_BUILD_DIR)

    print("Build Validation Layers and Tests")
    build_cmd = f'cmake --build . --config {args.configuration}'
    RunShellCmd(build_cmd, VVL_BUILD_DIR)

    print('Run vk_validation_stats.py')
    utils.make_or_exist_dirs(os.path.join(VVL_BUILD_DIR, 'layers', args.configuration.capitalize()))
    RunShellCmd(f'python3 ../scripts/vk_validation_stats.py ../{EXTERNAL_DIR_NAME}/Vulkan-Headers/registry/validusage.json -text layers/{args.configuration.capitalize()}/vuid_coverage_database.txt', VVL_BUILD_DIR)

#
# Prepare Loader for executing Layer Validation Tests
def BuildLoader(args):
    LOADER_DIR = RepoRelative("%s/Vulkan-Loader" % EXTERNAL_DIR_NAME)
    # Clone Loader repo
    if not os.path.exists(LOADER_DIR):
        print("Clone Loader Source Code")
        clone_loader_cmd = 'git clone https://github.com/KhronosGroup/Vulkan-Loader.git'
        RunShellCmd(clone_loader_cmd, EXTERNAL_DIR)

    print("Run update_deps.py for Loader Repository")
    update_cmd = 'python3 scripts/update_deps.py --dir external'
    RunShellCmd(update_cmd, LOADER_DIR)

    print("Run CMake for Loader")
    LOADER_BUILD_DIR = RepoRelative("%s/Vulkan-Loader/%s" % (EXTERNAL_DIR_NAME, BUILD_DIR_NAME))
    utils.make_or_exist_dirs(LOADER_BUILD_DIR)
    cmake_cmd = 'cmake -C ../external/helper.cmake -DCMAKE_BUILD_TYPE=%s ..' % args.configuration.capitalize()
    if IsWindows(): cmake_cmd = cmake_cmd + f' -A {args.arch}'
    RunShellCmd(cmake_cmd, LOADER_BUILD_DIR)

    print("Build Loader")
    build_cmd = f'cmake --build . --config {args.configuration}'
    RunShellCmd(build_cmd, LOADER_BUILD_DIR)

#
# Prepare Mock ICD for use with Layer Validation Tests
def BuildMockICD(args):
    if not os.path.exists(RepoRelative("%s/Vulkan-Tools" % EXTERNAL_DIR_NAME)):
        print("Clone Vulkan-Tools Repository")
        clone_tools_cmd = 'git clone https://github.com/KhronosGroup/Vulkan-Tools.git'
        RunShellCmd(clone_tools_cmd, EXTERNAL_DIR)

    print("Run CMake for ICD")
    ICD_BUILD_DIR = RepoRelative("%s/Vulkan-Tools/%s" % (EXTERNAL_DIR_NAME,BUILD_DIR_NAME))
    utils.make_or_exist_dirs(ICD_BUILD_DIR)
    cmake_cmd = \
        f'cmake -DCMAKE_BUILD_TYPE={args.configuration.capitalize()} -DBUILD_CUBE=NO -DBUILD_VULKANINFO=NO -DINSTALL_ICD=OFF -DVULKAN_HEADERS_INSTALL_DIR={EXTERNAL_DIR}/Vulkan-Headers/{BUILD_DIR_NAME}/install ..'
    RunShellCmd(cmake_cmd, ICD_BUILD_DIR)

    VVL_REG_DIR = "%s/Vulkan-Headers/registry" % EXTERNAL_DIR
    VT_SCRIPTS_DIR = "%s/Vulkan-Tools/scripts" % EXTERNAL_DIR

    print ("Geneating ICD Source Code")
    VT_ICD_DIR = "%s/Vulkan-Tools/icd/generated" % EXTERNAL_DIR
    LVL_GEN_SCRIPT = RepoRelative("scripts/lvl_genvk.py")
    typemap_cmd = 'python3 %s -registry %s/vk.xml vk_typemap_helper.h' % (LVL_GEN_SCRIPT, VVL_REG_DIR)
    RunShellCmd(typemap_cmd, VT_ICD_DIR)

    KVT_GEN_SCRIPT = "%s/Vulkan-Tools/scripts/kvt_genvk.py" % EXTERNAL_DIR
    icd_cpp_cmd = 'python3 %s -registry %s/vk.xml mock_icd.cpp' % (KVT_GEN_SCRIPT, VVL_REG_DIR)
    RunShellCmd(icd_cpp_cmd, VT_ICD_DIR)

    icd_h_cmd = 'python3 %s -registry %s/vk.xml mock_icd.h' % (KVT_GEN_SCRIPT, VVL_REG_DIR)
    RunShellCmd(icd_h_cmd, VT_ICD_DIR)

    print("Build Mock ICD")
    build_cmd = f'cmake --build . --target VkICD_mock_icd --config {args.configuration}'
    RunShellCmd(build_cmd, ICD_BUILD_DIR)

    # Copy json file into dir with ICD executable
    src_filename = RepoRelative("%s/Vulkan-Tools/icd/linux/VkICD_mock_icd.json" % EXTERNAL_DIR_NAME)
    dst_filename = RepoRelative("%s/Vulkan-Tools/%s/icd/VkICD_mock_icd.json" % (EXTERNAL_DIR_NAME, BUILD_DIR_NAME))
    shutil.copyfile(src_filename, dst_filename)

#
# Run the Layer Validation Tests
def RunVVLTests(args):
    print("Run Vulkan-ValidationLayer Tests using Mock ICD")
    os.chdir(PROJECT_ROOT)
    lvt_cmd = '%s/tests/vk_layer_validation_tests' % BUILD_DIR_NAME
    lvt_env = dict(os.environ)
    lvt_env['LD_LIBRARY_PATH'] = '%s/Vulkan-Loader/%s/loader' % (EXTERNAL_DIR, BUILD_DIR_NAME)
    lvt_env['VK_LAYER_PATH'] = '%s/%s/layers' % (PROJECT_ROOT, BUILD_DIR_NAME)
    lvt_env['VK_ICD_FILENAMES'] = '%s/Vulkan-Tools/%s/icd/VkICD_mock_icd.json' % (EXTERNAL_DIR, BUILD_DIR_NAME)
    subprocess.check_call(lvt_cmd.split(" "), env=lvt_env)

def GetArgParser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config', dest='configuration',
        metavar='CONFIG', action='store',
        choices=CONFIGURATIONS, default=DEFAULT_CONFIGURATION,
        help='Build target configuration. Can be one of: {0}'.format(
            ', '.join(CONFIGURATIONS)))
    parser.add_argument(
        '-a', '--arch', dest='arch',
        metavar='ARCH', action='store',
        choices=ARCHS, default=DEFAULT_ARCH,
        help=f'Target architecture. Can be one of: {ARCHS}')
    return parser

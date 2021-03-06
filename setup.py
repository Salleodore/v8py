#!/usr/bin/env python
from __future__ import print_function

import sys
import os
import stat
from contextlib import contextmanager
from subprocess import check_call
import multiprocessing

from setuptools import setup, find_packages, Extension, Command
from distutils.command.build_ext import build_ext as distutils_build_ext

MODE = 'native'

os.chdir(os.path.abspath(os.path.dirname(__file__)))

sources = list(map(lambda path: os.path.join('v8py', path),
              filter(lambda path: path.endswith('.cpp'),
                     os.listdir('v8py'))))
libraries = ['v8_libplatform', 'v8_base', 'v8_snapshot',
             'v8_libbase', 'v8_libsampler']
library_dirs = ['v8/out/{}'.format(MODE),
                'v8/out/{}/obj.target/src'.format(MODE)]
if sys.platform.startswith('linux'):
    libraries.append('rt')

extra_compile_args = ['-std=c++11']

if sys.platform.startswith('darwin'):
    extra_compile_args.append('-stdlib=libc++')

extension = Extension('_v8py',
                      sources=sources,
                      include_dirs=['v8py', 'v8/include'],
                      library_dirs=library_dirs,
                      libraries=libraries,
                      extra_compile_args=extra_compile_args,
                      )

@contextmanager
def cd(path):
    old_cwd = os.getcwd()
    try:
        yield os.chdir(path)
    finally:
        os.chdir(old_cwd)

DEPOT_TOOLS_PATH = os.path.join(os.getcwd(), 'depot_tools')
COMMAND_ENV = os.environ.copy()
COMMAND_ENV['PATH'] = DEPOT_TOOLS_PATH + os.path.pathsep + os.environ['PATH']
COMMAND_ENV.pop('CC', None)
COMMAND_ENV.pop('CXX', None)

def run(command):
    print(command)
    check_call(command, shell=True, env=COMMAND_ENV)

def v8_exists():
    def library_exists(library):
        if library == 'rt':
            return True
        lib_filename = 'lib{}.a'.format(library)
        for lib_dir in library_dirs:
            lib_path = os.path.join(lib_dir, lib_filename)
            if os.path.isfile(lib_path):
                return True
        print(lib_filename, 'not found')
        return False
    return all(library_exists(lib) for lib in libraries)

def get_v8():
    if not os.path.isdir('depot_tools'):
        print('installing depot tools')
        run('git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git')
        with cd('depot_tools'):
            with open('python', 'w') as python:
                print('#!/bin/sh', file=python)
                print('python2 "$@"', file=python)
            # Octal literals don't have the same syntax on python 2 and 3, so I use a decimal literal
            os.chmod('python', os.stat('python').st_mode | 73)
    else:
        print('updating depot tools')
        with cd('depot_tools'):
            run('git pull')

    if not os.path.isdir('v8/.git'):
        print('downloading v8')
        run('fetch --force v8')
    else:
        print('updating v8')
        with cd('v8'):
            run('gclient fetch')

    with cd('v8'):
        run('git checkout {}'.format('branch-heads/5.9'))
        run('gclient sync')

class BuildV8Command(Command):
    # currently no options
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass

    def run(self):
        if not v8_exists():
            get_v8()
            with cd('v8'):
                gypflags = '-Dv8_use_external_startup_data=0 -Dv8_enable_i18n_support=0 -Dv8_enable_inspector=1 -Dwerror=\'\' '
                run('make GYPFLAGS="{}" CFLAGS=-fPIC CXXFLAGS=-fPIC {} -j{}'.format(gypflags, MODE, multiprocessing.cpu_count()))

class build_ext(distutils_build_ext):
    def build_extension(self, ext):
        self.run_command('build_v8')

        distutils_build_ext.build_extension(self, ext)

with open('README.rst', 'r') as f:
    long_description = f.read()

setup(
    name='v8py',
    version='0.9.13',

    author='Theodore Dubois',
    author_email='tblodt@icloud.com',
    url='https://github.com/tbodt/v8py',

    description='Write Python APIs, then call them from JavaScript using the V8 engine.',
    long_description=long_description,

    license='LGPLv3',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
        'Topic :: Software Development :: Interpreters',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
    ],

    keywords=['v8', 'javascript'],

    packages=find_packages(exclude=['tests']),
    ext_modules=[extension],

    extras_require={
        'devtools': ['gevent', 'greenstack-greenlet', 'karellen-geventws'],
    },
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    cmdclass={
        'build_ext': build_ext,
        'build_v8': BuildV8Command,
    },
)

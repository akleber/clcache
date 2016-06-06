#!/usr/bin/env python
#
# This file is part of the clcache project.
#
# Copyright (c)
#   2016 Simon Warta (Kullo GmbH)
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
import clcache
from contextlib import contextmanager
import os
import subprocess
import sys
import unittest


PYTHON_BINARY = sys.executable
CLCACHE_SCRIPT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "clcache.py")


@contextmanager
def cd(target_directory):
    old_directory = os.getcwd()
    os.chdir(os.path.expanduser(target_directory))
    try:
        yield
    finally:
        os.chdir(old_directory)


class BaseTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        self.longMessage = True
        super(BaseTest, self).__init__(*args, **kwargs)


class TestCommandLineArguments(BaseTest):
    @unittest.skip("Do not run this test by default because it change user's cache settings")
    def testValidMaxSize(self):
        valid_values = ["1", "  10", "42  ", "22222222"]
        for value in valid_values:
            cmd = [PYTHON_BINARY, CLCACHE_SCRIPT, "-M", value]
            self.assertEqual(subprocess.call(cmd), 0, "Command must not fail for max size: '" + value + "'")

    def testInvalidMaxSize(self):
        invalid_values = ["ababa", "-1", "0", "1000.0"]
        for value in invalid_values:
            cmd = [PYTHON_BINARY, CLCACHE_SCRIPT, "-M", value]
            self.assertNotEqual(subprocess.call(cmd), 0, "Command must fail for max size: '" + value + "'")


class TestCompileRuns(BaseTest):
    def testBasicCompileC(self):
        cmd = [PYTHON_BINARY, CLCACHE_SCRIPT, "/nologo", "/c", "tests\\fibonacci.c"]
        subprocess.check_call(cmd)

    def testBasicCompileCpp(self):
        cmd = [PYTHON_BINARY, CLCACHE_SCRIPT, "/nologo", "/EHsc", "/c", "tests\\fibonacci.cpp"]
        subprocess.check_call(cmd)

    def testCompileLinkRunC(self):
        cmd = [PYTHON_BINARY, CLCACHE_SCRIPT, "/nologo", "/c", "tests\\fibonacci.c", "/Fofibonacci_c.obj"]
        subprocess.check_call(cmd)
        cmd = ["link", "/nologo", "/OUT:fibonacci_c.exe", "fibonacci_c.obj"]
        subprocess.check_call(cmd)
        cmd = ["fibonacci_c.exe"]
        output = subprocess.check_output(cmd).decode("ascii").strip()
        self.assertEqual(output, "0 1 1 2 3 5 8 13 21 34 55 89 144 233 377")

    def testCompileLinkRunCpp(self):
        cmd = [PYTHON_BINARY, CLCACHE_SCRIPT, "/nologo", "/EHsc", "/c", "tests\\fibonacci.cpp", "/Fofibonacci_cpp.obj"]
        subprocess.check_call(cmd)
        cmd = ["link", "/nologo", "/OUT:fibonacci_cpp.exe", "fibonacci_cpp.obj"]
        subprocess.check_call(cmd)
        cmd = ["fibonacci_cpp.exe"]
        output = subprocess.check_output(cmd).decode("ascii").strip()
        self.assertEqual(output, "0 1 1 2 3 5 8 13 21 34 55 89 144 233 377")

    def testRecompile(self):
        cmd = [PYTHON_BINARY, CLCACHE_SCRIPT, "/nologo", "/EHsc", "/c", "tests\\recompile1.cpp"]
        subprocess.check_call(cmd) # Compile once
        subprocess.check_call(cmd) # Compile again

    def testRecompileObjectSetSameDir(self):
        cmd = [PYTHON_BINARY, CLCACHE_SCRIPT, "/nologo", "/EHsc", "/c", "tests\\recompile2.cpp", "/Forecompile2_custom_object_name.obj"]
        subprocess.check_call(cmd) # Compile once
        subprocess.check_call(cmd) # Compile again

    def testRecompileObjectSetOtherDir(self):
        cmd = [PYTHON_BINARY, CLCACHE_SCRIPT, "/nologo", "/EHsc", "/c", "tests\\recompile3.cpp", "/Fotests\\output\\recompile2_custom_object_name.obj"]
        subprocess.check_call(cmd) # Compile once
        subprocess.check_call(cmd) # Compile again


class TestHits(BaseTest):
    def testHitsSimple(self):
        cmd = [PYTHON_BINARY, CLCACHE_SCRIPT, "/nologo", "/EHsc", "/c", r'tests\hits-and-misses\hit.cpp']
        subprocess.check_call(cmd) # Ensure it has been compiled before

        cache = clcache.ObjectCache()
        oldHits = clcache.CacheStatistics(cache).numCacheHits()
        subprocess.check_call(cmd) # This must hit now
        newHits = clcache.CacheStatistics(cache).numCacheHits()
        self.assertEqual(newHits, oldHits + 1)


class TestPrecompiledHeaders(BaseTest):
    def testSampleproject(self):
        with cd(os.path.join("tests", "precompiled-headers")):
            cpp = PYTHON_BINARY + " " + CLCACHE_SCRIPT

            cmd = ["nmake", "/nologo"]
            subprocess.check_call(cmd, env=dict(os.environ, CPP=cpp))

            cmd = ["myapp.exe"]
            subprocess.check_call(cmd)

            cmd = ["nmake", "/nologo", "clean"]
            subprocess.check_call(cmd, env=dict(os.environ, CPP=cpp))

            cmd = ["nmake", "/nologo"]
            subprocess.check_call(cmd, env=dict(os.environ, CPP=cpp))


class TestHeaderChange(BaseTest):
    def _clean(self):
        if os.path.isfile("main.obj"):
            os.remove("main.obj")
        if os.path.isfile("main.exe"):
            os.remove("main.exe")

    def _compileAndLink(self, environment = os.environ):
        cmdCompile = [PYTHON_BINARY, CLCACHE_SCRIPT, "/nologo", "/EHsc", "/c", "main.cpp"]
        cmdLink = ["link", "/nologo", "/OUT:main.exe", "main.obj"]
        subprocess.check_call(cmdCompile, env=environment)
        subprocess.check_call(cmdLink, env=environment)

    def testDirect(self):
        with cd(os.path.join("tests", "header-change")):
            self._clean()

            with open("version.h", "w") as header:
                header.write("#define VERSION 1")

            self._compileAndLink()
            cmdRun = [os.path.abspath("main.exe")]
            output = subprocess.check_output(cmdRun).decode("ascii").strip()
            self.assertEqual(output, "1")

            self._clean()

            with open("version.h", "w") as header:
                header.write("#define VERSION 2")

            self._compileAndLink()
            cmdRun = [os.path.abspath("main.exe")]
            output = subprocess.check_output(cmdRun).decode("ascii").strip()
            self.assertEqual(output, "2")

    def testNoDirect(self):
        with cd(os.path.join("tests", "header-change")):
            self._clean()

            with open("version.h", "w") as header:
                header.write("#define VERSION 1")

            self._compileAndLink(dict(os.environ, CLCACHE_NODIRECT="1"))
            cmdRun = [os.path.abspath("main.exe")]
            output = subprocess.check_output(cmdRun).decode("ascii").strip()
            self.assertEqual(output, "1")

            self._clean()

            with open("version.h", "w") as header:
                header.write("#define VERSION 2")

            self._compileAndLink(dict(os.environ, CLCACHE_NODIRECT="1"))
            cmdRun = [os.path.abspath("main.exe")]
            output = subprocess.check_output(cmdRun).decode("ascii").strip()
            self.assertEqual(output, "2")


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python

import subprocess
import sys
import os

path_to_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))

def docker_check():
    print("Running docker check...")
    try:
        subprocess.run(["docker", "buildx", "build", 
                        "--platform", "linux/arm64",
                        "-t", "img_name",
                        "--load", "."],
                       timeout=200,
                       check=True,
                       cwd = path_to_root)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(error)
        exit(1)
    print("OK\n")

def print_help():
    print(__file__ + " <options, if no args syntax/lint check and unittests are run>\n")
    print("-x --syntax\t\tEnable syntax check")
    print("-l --lint\t\tEnable lint check")
    print("-u --unittests\t\tEnable unittests")
    print("-s --systemtests\tEnable systemtests")
    print("-d --docker\tEnable docker build test")
    print("-h --help\t\tThis help")


if __name__ == '__main__':
    run_docker = False
    run_syntax = False
    run_lint = False
    run_unit = False
    run_system = False

    if len(sys.argv) == 1:
        # Default
        run_docker = True
        # run_syntax = True
        # run_lint = True
        # run_unit = True
    else:
        for arg in sys.argv[1:]:
            if arg == "-h" or "help" in arg.lower():
                print_help()
                if len(sys.argv) == 2:
                    exit(0)
                else:
                    exit(1)
            elif arg == "-d" or "--docker" in arg.lower():
                run_docker = True
            elif arg == "-x" or "syntax" in arg.lower():
                # run_syntax = True
                print("Syntax check not yet supported")
            elif arg == "-l" or "lint" in arg.lower():
                # run_lint = True
                print("Lint check not yet supported")
            elif arg == "-u" or "unittest" in arg.lower():
                # run_unit = True
                print("Unit tests not yet supported")
            elif arg == "-s" or "systemtest" in arg.lower():
                # run_system = True
                print("Systemtests not yet supported")
            else:
                print("Error: Unknown argument " + arg)
                print_help()
                exit(1)

    if run_docker:
        docker_check()
    # if run_syntax:
        # syntax_check()
    # if run_lint:
        # lint_check()
    # if run_unit:
        # unittests()
    # if run_system:
        # systemtests()

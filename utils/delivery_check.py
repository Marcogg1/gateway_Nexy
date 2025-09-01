#!/usr/bin/env python

import subprocess
import shutil
import sys
import os

path_to_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))

def syntax_check():
    """
    Check for syntax errors
    -f: force rebuild
    -q: output only errors
    -x <regex>: if the regex produces a match, the file is skipped
    -r: maximum recursion level for subdirectories
    """
    print("Syntax check...")
    stderr = ""
    try:
        subprocess.run(["python", "-m", "compileall", "-f", "-q", "../utest", "../utils", "../src", "../test",
                        "-x", "buildroot-",
                        "-r", "2"],
                       timeout=20,
                       check=True,
                       stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(error)
        print(stderr)
        exit(1)
    print("OK\n")

def lint_check():
    """
    Check for lint errors
    :return:
    """
    print("Lint check...")
    stderr = ""
    try:
        command = "python -m pylint --errors-only --ignore=config src/"
        subprocess.run(command.split(),
                       timeout=90,
                       check=True,
                       cwd=path_to_root,
                       stderr=subprocess.STDOUT)

        command = "python -m pylint --rcfile=.pylintrc --errors-only utils/"
        subprocess.run(command.split(),
                       timeout=90,
                       check=True,
                       cwd=path_to_root,
                       stderr=subprocess.STDOUT)

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(error)
        print(stderr)
        exit(1)
    print("OK\n")

def unittests():
    """
    Run unittests
    """
    print("Unittests...")
    stderr = ""
    try:
        subprocess.run(["python", "-m", "pytest", "utest", "--junitxml=../output/host/unittests.xml",
                        "--cov=src", "--cov-report", "term-missing"],
                       timeout=(60 * 3),
                       check=True,
                       cwd=path_to_root,
                       stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(error)
        print(stderr)
        exit(1)
    print("OK\n")

def annotation_check():
    """
    Run an annotation check (mypy)
    """
    print("Running mypy check...")
    stderr = ""
    try:
        subprocess.run(["python", "-m", "mypy", "."],
                       timeout=60,
                       check=True,
                       cwd=path_to_root,
                       encoding='utf-8',
                       stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(error)
        print(stderr)
        exit(1)
    print("OK\n")

def docker_syntax_check():
    """
    Run docker build check without building it
    """
    stderr = ""
    try:
        subprocess.run(["docker", "buildx", "build", "--check", "."],
                       timeout=200,
                       check=True,
                       cwd=path_to_root,
                       encoding='utf-8',
                       stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(error)
        print(stderr)
        print("Is the docker program started?")
        exit(1)
    print("OK\n")

def docker_build_check():
    """
    Attempting docker build
    """
    print("Running docker build check...")
    stderr = ""
    try:
        subprocess.run(["docker", "buildx", "build", 
                        "--platform", "linux/arm64",
                        "-t", "delivery_check_img",
                        "--load", "."],
                       timeout=200,
                       check=True,
                       cwd=path_to_root,
                       encoding='utf-8',
                       stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(error)
        print(stderr)
        print("Is the docker program started?")
        exit(1)
    print("OK\n")

def print_help():
    print(__file__ + " <options, if no args syntax/lint check and unittests are run>\n")
    print("-a --lint\t\tEnable annotations check")
    print("-x --syntax\t\tEnable syntax check")
    print("-l --lint\t\tEnable lint check")
    print("-u --unittests\t\tEnable unittests")
    print("-s --systemtests\tEnable systemtests")
    print("-ds --docker\tEnable docker syntax test")
    print("-db --docker\tEnable docker build test")
    print("-h --help\t\tThis help")


if __name__ == '__main__':
    run_docker_syntax = False
    run_docker_build = False
    run_mypy = False
    run_syntax = False
    run_lint = False
    run_unit = False
    run_system = False

    if len(sys.argv) == 1:
        # Default
        run_docker_syntax = True
        run_docker_build = True
        run_mypy = True
        run_syntax = True
        run_lint = True
        run_unit = True
    else:
        for arg in sys.argv[1:]:
            if arg == "-h" or "help" in arg.lower():
                print_help()
                if len(sys.argv) == 2:
                    exit(0)
                else:
                    exit(1)
            elif arg == '-ds' or "--docker-syntax" in arg.lower():
                run_docker_syntax = True
            elif arg == "-db" or "--docker-build" in arg.lower():
                run_docker_build = True
            elif arg == "-a" or "--annotations" in arg.lower():
                run_mypy = True
            elif arg == "-x" or "syntax" in arg.lower():
                run_syntax = True
            elif arg == "-l" or "lint" in arg.lower():
                run_lint = True
            elif arg == "-u" or "unittest" in arg.lower():
                run_unit = True
            elif arg == "-s" or "systemtest" in arg.lower():
                # run_system = True
                print("Systemtests not yet supported")
            else:
                print("Error: Unknown argument " + arg)
                print_help()
                exit(1)

    
    if run_docker_syntax:
        docker_syntax_check()
    if run_docker_build:
        docker_build_check()
    if run_mypy:
        annotation_check()
    if run_syntax:
        syntax_check()
    if run_lint:
        lint_check()
    if run_unit:
        unittests()
    # if run_system:
        # systemtests()

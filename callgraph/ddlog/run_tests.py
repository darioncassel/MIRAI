from sys import argv
from pathlib import Path
from subprocess import run


def exec_test(test_path):
    # Gather expected test results
    expected_set = set()
    with open(test_path, 'r') as test_f:
        lines = test_f.readlines()
        for line in lines:
            if line.startswith('# expect '):
                expected = line.split('# expect ')[1].strip()
                if expected:
                    expected_set.add(expected)
    # Run test and get actual results
    cmd = f'./base_ddlog/target/release/base_cli < {test_path}'
    res = run(cmd, shell=True, capture_output=True)
    output = res.stdout + res.stderr
    actual_set = set()
    for line in output.decode('utf-8').split('\n'):
        line = line.strip()
        if line:
            actual_set.add(line)
    # Compare sets
    if expected_set == actual_set:
        return None
    else:
        return (expected_set, actual_set)


def main(args):
    verbose = (args[0] == '-v') if args else False
    tests_dir = Path('./tests')
    all_tests = [x for x in tests_dir.glob('*.dat')]
    print('Beginning testing...')
    for test_path in all_tests:
        diff = exec_test(test_path)
        if diff:
            expected, actual = diff
            print(f'Test case failed: {test_path}')
            if verbose:
                print(f'Expected:')
                for line in sorted(list(expected)):
                    print(f'# expect {line}')
                print(f'Actual:')
                for line in sorted(list(actual)):
                    print(f'# expect {line}')
            else:
                print(f'Diff:')
                for line in sorted(list(expected - actual)):
                    print(f'- # expect {line}')
                for line in sorted(list(actual - expected)):
                    print(f'+ # expect {line}')
        else:
            print(f'Test case successful: {test_path}')
    print('Done.')


if __name__ == "__main__":
    main(argv[1:])

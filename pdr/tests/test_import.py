import subprocess
import ast


def test_delayed_import():
    imports_to_delay = ['numpy', 'pandas']
    commands = f"import sys; import pdr; " \
               f"print(not any(module in sys.modules for module in {imports_to_delay}))"
    out = run_isolated(commands)
    assert ast.literal_eval(out)


def run_isolated(commands_for_interpreter):

    p = subprocess.run(['python', '-c', commands_for_interpreter],
                       capture_output=True,
                       text=True)
    stdout = p.stdout
    return stdout

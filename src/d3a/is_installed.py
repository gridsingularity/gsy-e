
def is_installed(module_name):
    try:
        __import__(module_name)
        return True
    except ModuleNotFoundError:
        return False

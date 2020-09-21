import functools

def cases(cases):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args):
            print('Testing ', f.__name__)
            for c in cases:
                new_args = args + (c if isinstance(c, tuple) else (c,))

                try:
                    f(*new_args)
                except AssertionError as aerror:
                    print('Failed with args=', new_args[1:])
                    raise aerror
            print('OK')
        return wrapper
    return decorator

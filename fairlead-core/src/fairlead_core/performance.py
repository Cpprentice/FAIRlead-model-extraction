try:
    from line_profiler import profile
except ImportError:
    # Create drop in replacement that does nothing if the profiler is not installed
    profile = lambda x: x

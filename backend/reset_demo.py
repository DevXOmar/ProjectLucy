try:
    from .seed import seed
except ImportError:
    from seed import seed

if __name__ == "__main__":
    seed()

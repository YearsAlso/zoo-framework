from zoo_framework.core import worker_threads,Master
import threads

def main():
    master = Master(worker_count=30)
    master.run()


if __name__ == '__main__':
    main()

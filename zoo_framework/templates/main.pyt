from zoo_framework.core import Master


def main():
    master = Master(worker_count=5)
    master.run()


if __name__ == '__main__':
    main()

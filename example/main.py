from zoo_framework.core import Master, worker_list
import threads


def main():
    master = Master(1)
    master.run()


if __name__ == '__main__':
    main()

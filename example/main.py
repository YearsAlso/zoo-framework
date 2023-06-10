from zoo_framework.core import Master, worker_register
import threads
import asyncio


def main():
    master = Master(1)
    master.run()


if __name__ == '__main__':
    main()

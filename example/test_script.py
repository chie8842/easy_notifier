

from time import sleep
from easy_notifier import easy_notifier


@easy_notifier('config.ini')
def main():
    print("sleep 10")
    sleep(2)
    print("slept 10")
    return 0


if __name__ == '__main__':
    main()


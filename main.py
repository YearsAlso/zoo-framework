from core.aop import application
from core.aop.scan_path import scanModule


@application(name="MainApplication")
@scanModule(path="test.*")
class MainApplication:
    @staticmethod
    def main():
        pass


if __name__ == '__main__':
    MainApplication().main()

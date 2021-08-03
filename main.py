from core.aop import application
from core.aop.scan_path import scanModule
from core.master import MasterApplication


@application(name="MainApplication")
@scanModule(path="test.*")
class MainApplication:
    @staticmethod
    def main():
        MasterApplication.run("MainApplication")



if __name__ == '__main__':
    MainApplication().main()

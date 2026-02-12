import os
import shutil


class FileUtils:
    @classmethod
    def dir_exists(cls, path):
        return os.path.exists(path)

    @classmethod
    def file_exists(cls, path):
        if cls.is_dir(path):
            return False
        return os.path.exists(path)

    @classmethod
    def get_file_parent(cls, path):
        return os.path.dirname(path)

    @classmethod
    def get_file_name(cls, path):
        return os.path.basename(path)

    @classmethod
    def mkdir(cls, path):
        if cls.dir_exists(path):
            return
        os.mkdir(path)

    @classmethod
    def dir_exists_and_create(cls, path) -> bool:
        if cls.dir_exists(path):
            return True

        os.makedirs(path)
        return True

    @classmethod
    def is_dir(cls, path):
        os.path.isdir(path)

    @classmethod
    def file_remove(cls, path):
        if not cls.file_exists(path):
            return

        os.remove(path)

    @classmethod
    def get_file_size(cls, path):
        if not cls.file_exists(path):
            raise Exception("File %s not found" % path)

        if not os.path.isfile(path):
            raise Exception("File %s not found" % path)

        return os.path.getsize(path)

    @classmethod
    def create_file(cls, path):
        file = open(path, 'w')
        file.close()

    @classmethod
    def copy_file(cls, src_path, target_path):
        shutil.copy(src_path, target_path)

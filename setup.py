from distutils.core import setup

from com.novikov.rfid import __version__


setup(
    name='RFID',
    version=__version__,
    packages=['com', 'com.novikov', 'com.novikov.rfid'],
    url='https://github.com/ilia-novikov/RFID',
    license='GNU GPL v3',
    author='ilia Novikov',
    author_email='ilia.novikov@live.ru',
    description='Simple application, that uses MongoDB to control access via RFID cards',
    requires=['pymongo', 'pythondialog', 'pyserial']
)

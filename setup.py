from setuptools import setup
import os

this_dir = os.path.abspath(os.path.dirname(__file__))
REQUIREMENTS = filter(None, open(
    os.path.join(this_dir, 'requirements.txt')).read().splitlines())

setup(
    name='sanic_limiter',
    version='0.1.2',
    description='Provides rate limiting features for Sanic. Supports in-memory, redis and memcache as storage.',
    url='https://github.com/bohea/sanic-limiter',
    author='bohea',
    author_email='libin375(at)163.com',
    license='MIT',
    packages=['sanic_limiter'],
    install_requires=list(REQUIREMENTS),
    zip_safe=False,
    keywords=['rate', 'limit', 'sanic', 'redis', 'memcache'],
    classifiers=[
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)

SETUP_INFO = dict(
    name='appypod',
    version='0.1',
    description="appy.pod for Python 3",
    license='Free BSD',
    test_suite='tests',
    author='Luc Saffre',
    author_email='luc@saffre-rumma.net',
    url="http://appypod.lino-framework.org",
    install_requires = ['future'],
    long_description="""\

The `appypod` project is a partial redistribution of Gaetan Delannay's
`Appy framework <http://appyframework.org/>`__ in order to make
`appy.pod` available under Python 3.

Note that it is only an *excerpt* of the full Appy framework: the
`pod` subpackage and a few others which are needed for pod: utils,
model, ui, http and xml.

**Why**

Gaetan is advancing with porting his appy framework to Python 3, and
his work is published on `forge.pallavi.be
<https://forge.pallavi.be/projects/appy-python-3>`__, and we can
easily check out a copy of the repository::

    $ svn checkout https://svn.forge.pallavi.be/appy-python-3

But this repository cannot be installed in a standard way because it
has no file `setup.py`.  Gaetan "installs" it by adding into his
`site-packages` a symbolic link to the `trunk` directory of the
repository.  We therefore cannot specify it in a `requirements.txt
<https://pip.readthedocs.io/en/1.1/requirements.html>`__ file.

This repository has only a minimal test suite, but it is also being
tested in the test suite of the Lino framework at
https://travis-ci.org/lino-framework/book

**Manual changes by LS**

I added files :file:`setup.py`, :file:`tasks.py`,
:file:`tests/__init__.py` and :file:`appy/setup_info.py`.

I manually fixed the following places which had trivial errors::

  File "appy/pod/renderer.py", line 247, in renderXhtml
    if isinstance(s, unicode): s = s.encode('utf-8')
  NameError: unicode

  File "appy/pod/elements.py", line 170, in evaluate
    res = res.decode('utf-8')
  AttributeError: 'str' object has no attribute 'decode'

  File "appy/pod/elements.py", line 182, in evaluate
    res = unicode(res)
  NameError: name 'unicode' is not defined

  File "appy/utils/dates.py", line 66
    except DateTime.DateError, de:
                             ^
  SyntaxError: invalid syntax

  File "appy/pod/test/Tester.py", line 101
    exec 'import %s' % contextPkg
                   ^
  SyntaxError: Missing parentheses in call to 'exec'

**Others**

Christian Jauvin contributed a fix to this distribution.

Stefan Klug started a similar attempt in 2015:
https://github.com/stefanklug/appypod



""",
    classifiers="""\
Programming Language :: Python
Programming Language :: Python :: 3.4
Programming Language :: Python :: 3.5
Development Status :: 5 - Production/Stable
Intended Audience :: Developers
License :: OSI Approved :: BSD License
Natural Language :: English
Operating System :: OS Independent""".splitlines())

SETUP_INFO.update(packages=[n for n in """
appy
appy.pod
appy.pod.test
appy.pod.test.contexts
appy.http
appy.model
appy.model.fields
appy.px
appy.ui
appy.utils
appy.xml
""".splitlines() if n])

SETUP_INFO.update(package_data=dict())

=======================
The ``appypod`` package
=======================


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


**Manual changes by LS**

I added a file setup.py, tasks.py and appy/setup_info.py

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




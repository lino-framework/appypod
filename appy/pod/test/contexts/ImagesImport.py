import os.path
import appy

def getAppyPath():
    return os.path.dirname(appy.__file__)

xhtmlChunk = '''
<img alt="" src="./images/linux.jpg"
     style="height:200px; width:100px" title="Image"/>
<img alt="" src="./images/linux.jpg"
     style="height:200px; width:100px; float:right;" title="Image"/>
<!-- Image with no defined width or height -->
<img src="./images/imio.png"/>
<!-- Image with html attributes "width" and "height" -->
<img src="./images/imio.png" width="74px" height="145px"/>
<p></p>
<table>
 <tbody><tr><td><p><img alt="" src="./images/linux.jpg"/></p></td></tr></tbody>
</table>
'''

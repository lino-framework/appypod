# -*- coding: utf-8 -*-
xhtmlInput = '''
<p>Hello.</p>
<h2>Heading One</h2>
Blabla.<br />
<h3>SubHeading then.</h3>
Another blabla.<br /><br /><br />
<p style="font-weight:bold">Hello CentreCentre</p>
<div>In a div</div>
'''
# I need a class
class D:
    def getAt1(self):
        return xhtmlInput
dummy = D()

xhtmlInput2='''
<p style="font-style:italic">Mapped to style_1.</p>
'''

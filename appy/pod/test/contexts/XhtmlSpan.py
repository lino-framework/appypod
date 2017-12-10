# -*- coding: utf-8 -*-
xhtmlInput = '''<strong>A<strong>B</strong></strong>
  <p>Text "Hello" in the following span tag will be applied an
  inline style: <span class="Variable">Hello</span> end.</p>
  <p>And here, style <span class="TELE">Teletype</span> will be applied</p>
  <p><br/>Here, underline and bold were not noth applied</p>
  <p><u><strong>Text :</strong></u></p>
  <p><b><u>Text :</u></b></p>
  <p><b><u>Text :</u> continued</b></p>
  <p>In the text below, some chars were deleted:</p>
  <p>My text,<span> text with space before</span> text
     text,<span> text with space before and after </span>and text.</p>
  <p><u><s><strong>Bold strike underline</strong></s></u></p>
  <p><b><i><s>Bold strike italic</s></i>;</b></p>
  <p style="font-size: small">Small</p>
  <p><em>Tralala<br />
   <strong>- 1 ;<br />
   - 2 ;<br />
    - 3 ;<br />
   - 4.</strong></em>
  </p>
  <!-- The space before the star was removed -->
  <p><em><em>Texte</em></em><b><u> *texte</u></b></p>
  <p style="text-align:justify"><em><em>Texte </em></em><em><em>texte texte</em></em><em><em> texte </em></em><em><em>texte</em></em><em><em> texte.</em></em></p>
  <!-- The "strike" was not applied throughout the whole paragraph -->
  <p><s><u>test </u><u>...</u>must be strike here <u>.</u></s></p>
'''

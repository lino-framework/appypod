'''User-interface module'''

# ------------------------------------------------------------------------------
import os.path

# ------------------------------------------------------------------------------
class UiConfig:
    '''Represents uer-interface configuration for your app'''
    fonts = '"Lucida Grande","Lucida Sans Unicode",Helvetica,Arial,Verdana,' \
            'sans-serif'

    def __init__(self, banner='banner.png', fonts=fonts):
        # The top banner
        self.banner = banner
        # Fonts in use
        self.fonts = fonts

    def getBannerName(self, dir):
        '''If your site uses at least one RTL (right-to-left) language, you must
           propose a banner whose name is self.banner, suffixed with "rtl".'''
        res = self.banner
        if dir == 'rtl': res = '%srtl%s' % os.path.splitext(res)
        return res
# ------------------------------------------------------------------------------

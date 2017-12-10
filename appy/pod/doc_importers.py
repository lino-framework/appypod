# ~license~
# ------------------------------------------------------------------------------
import os,os.path,stat,time,shutil,struct,random,urllib.parse,imghdr,uuid
import appy.pod
from appy import utils
from appy.pod import PodError
from appy.model.utils import Object as O
from appy.pod.odf_parser import OdfEnvironment
from appy.utils.path import getOsTempFolder
from appy.ui.css import CssStyles
from appy.http.client import Resource

# ------------------------------------------------------------------------------
px2cm = 44.173513561
FILE_NOT_FOUND = "'%s' does not exist or is not a file."
PDF_TO_IMG_ERROR = 'A PDF file could not be converted into images. Please ' \
                   'ensure that Ghostscript (gs) is installed on your ' \
                   'system and the "gs" program is in the path.'
CONVERT_ERROR = 'Program "convert" (imagemagick) must be installed and ' \
  'in the path for performing this operation. If you wanted to convert a ' \
  'SVG file into a PNG file, conversion of SVG files must also be enabled. ' \
  'On Ubuntu: apt-get install librsvg2-bin'
TO_PDF_ERROR = 'ConvertImporter error while converting a doc to PDF: %s.'

# ------------------------------------------------------------------------------
def getUuid(removeDots=False):
    '''Get a unique id (ie, for images/documents to be imported into an ODT
       document).'''
    r = uuid.uuid4().hex
    if removeDots: r = r.replace('.', '')
    return r

# ------------------------------------------------------------------------------
class DocImporter:
    '''Base class used for importing external content into a pod template (an
       image, another pod template, another odt document...'''
    def __init__(self, content, at, format, renderer):
        self.content = content
        self.renderer = renderer
        # If content is None, p_at tells us where to find it (file path, url...)
        self.at = at
        # Check and standardize p_at
        self.format = format
        if at:
            self.at = self.checkAt(at)
        self.res = u''
        self.ns = renderer.currentParser.env.namespaces
        # Unpack some useful namespaces
        self.textNs = self.ns[OdfEnvironment.NS_TEXT]
        self.linkNs = self.ns[OdfEnvironment.NS_XLINK]
        self.drawNs = self.ns[OdfEnvironment.NS_DRAW]
        self.svgNs = self.ns[OdfEnvironment.NS_SVG]
        self.tempFolder = renderer.tempFolder
        self.importFolder = self.getImportFolder()
        # Create the import folder if it does not exist
        if not os.path.exists(self.importFolder): os.mkdir(self.importFolder)
        self.importPath = self.getImportPath()
        # A link to the global fileNames dict (explained in renderer.py)
        self.fileNames = renderer.fileNames
        if self.at:
            # Move the file within the ODT, if it is an image and if this image
            # has not already been imported.
            self.importPath = self.moveFile()
        else:
            # We need to dump the file content (in self.content) in a temp file
            # first. self.content may be binary, a file handler or a
            # FileWrapper.
            if isinstance(self.content, utils.FileWrapper):
                self.content.dump(self.importPath)
            else:
                if isinstance(self.content, file):
                    fileContent = self.content.read()
                else:
                    fileContent = self.content
                f = open(self.importPath, 'wb')
                f.write(fileContent)
                f.close()
        # Some importers add specific attrs, through method init

    def checkAt(self, at, raiseOnError=True):
        '''Check and apply some transform to p_at'''
        # Resolve relative path
        if at.startswith('./'): at = os.path.join(os.getcwd(), at[2:])
        # Checks that p_at corresponds to an existing file if given
        if raiseOnError and not os.path.isfile(at):
            raise PodError(FILE_NOT_FOUND % at)
        return at

    def getImportFolder(self):
        '''This method gives the path where to dump the content of the document
           or image. In the case of a document it is a temp folder; in the case
           of an image it is a folder within the ODT result.'''
        return '%s/docImports' % self.tempFolder # For most importers

    def getImportPath(self):
        '''Gets the path name of the file to dump on disk (within the ODT for
           images, in a temp folder for docs).'''
        format = self.format
        if not format or (format == 'image'):
            at = self.at
            if at.startswith('http') or not os.path.exists(at):
                # We will know it only after the HTTP GET (or never if the file
                # does not exist)
                self.format = ''
            else:
                self.format = os.path.splitext(at)[1][1:]
        fileName = '%s.%s' % (getUuid(), self.format)
        return os.path.abspath('%s/%s' % (self.importFolder, fileName))

    def moveFile(self):
        '''In the case "self.at" was used, we may want to move the file at
           self.at within the ODT result in self.importPath (for images) or do
           nothing (for docs). In the latter case, the file to import stays
           at self.at, and is not copied into self.importPath. So the previously
           computed self.importPath is not used at all.'''
        return self.at

class OdtImporter(DocImporter):
    '''This class allows to import the content of another ODT document into a
       pod template.'''

    # POD manages page breaks by inserting a paragraph whose style inserts a
    # page break before or after it.
    pageBreakTemplate = '<text:p text:style-name="podPageBreak%s"></text:p>'
    pageBreaks = O(before=pageBreakTemplate % 'Before',
                   after=pageBreakTemplate % 'After')

    def init(self, pageBreakBefore, pageBreakAfter):
        '''OdtImporter-specific constructor'''
        self.pageBreakBefore = pageBreakBefore
        self.pageBreakAfter = pageBreakAfter

    def getPageBreakAfterCount(self):
        '''Returns the number of page breaks that must be inserted after
           sub-document insertion.'''
        if self.pageBreakAfter == 'duplex':
            # Read metadata about the sub-ODT, containing its number of pages
            metadata = MetadataReader(self.importPath).run()
            odd = (metadata.pagecount % 2) == 1
            r = odd and 2 or 1            
        else:
            r = 1
        return r

    def run(self):
        '''Import the content of a sub-ODT document'''
        # Insert a page break before importing the doc if needed
        if self.pageBreakBefore: self.res += self.pageBreaks.before
        # Import the external odt document
        self.res += '<%s:section %s:name="PodImportSection%f">' \
                    '<%s:section-source %s:href="%s" ' \
                    '%s:filter-name="writer8"/></%s:section>' % (
                        self.textNs, self.textNs, time.time(), self.textNs,
                        self.linkNs, self.importPath, self.textNs, self.textNs)
        # Insert (a) page break(s) after importing the doc if needed
        if self.pageBreakAfter:
            nb = self.getPageBreakAfterCount()
            for i in range(nb):
                self.res += self.pageBreaks.after
            # Note that if there is no more document content after the last page
            # break, it will not be visible.
        return self.res

class PodImporter(DocImporter):
    '''This class allows to import the result of applying another POD template,
       into the current POD result.'''
    def init(self, context, pageBreakBefore, pageBreakAfter):
        '''PodImporter-specific constructor'''
        self.context = context
        self.pageBreakBefore = pageBreakBefore
        self.pageBreakAfter = pageBreakAfter

    def forceSubLoCall(self, mainRenderer):
        '''In some cases, we must force LO call when rendering the sub-pod'''
        # Force LO call if we are inserting sub-documents in "duplex" mode.
        # Indeed, in this case, we will need to know the exact number of pages
        # for every sub-document. We will call LO for that purpose: it will
        # produce correct document statistics within meta.xml, which is not the
        # case for an ODT document produced by POD without forcing OO call
        # (stats are those from the document template and not from the pod
        # result).
        if self.pageBreakAfter == 'duplex':
            r = True
        else:
            # Use the parameter as defined in the main renderer
            r = mainRenderer.forceOoCall
        return r

    def run(self):
        # This feature is only available in the open source version
        if utils.commercial: raise utils.CommercialError()
        # Define where to store the pod result in the temp folder
        r = self.renderer
        # Define where to store the ODT result
        op = os.path
        resOdt = op.join(self.getImportFolder(), '%s.odt' % getUuid())
        # Force LO call when rendering the sub-pod in "duplex" mode
        forceLoCall = self.forceSubLoCall(r)
        # The POD template is in self.importPath
        renderer = r.__class__(self.importPath, self.context, resOdt,
          pythonWithUnoPath=r.pyPath, ooPort=r.ooPort, forceOoCall=forceLoCall,
          imageResolver=r.imageResolver, renamePageStyles=True)
        renderer.stylesManager.stylesMapping = r.stylesManager.stylesMapping
        renderer.run()
        # The POD result is in "resOdt". Import it into the main POD result
        # using an OdtImporter.
        odtImporter = OdtImporter(None, resOdt, 'odt', self.renderer)
        odtImporter.init(self.pageBreakBefore, self.pageBreakAfter)
        return odtImporter.run()

class PdfImporter(DocImporter):
    '''This class allows to import the content of a PDF file into a pod
       template. It calls gs to split the PDF into images and calls the
       ImageImporter for importing it into the result.'''
    # Ghostscript devices that can be used for converting PDFs into images
    gsDevices = {'jpeg': 'jpg', 'jpeggray': 'jpg',
                 'png16m': 'png', 'pnggray': 'png'}

    def run(self):
        # This feature is only available in the open source version
        if utils.commercial: raise utils.CommercialError()
        imagePrefix = os.path.splitext(os.path.basename(self.importPath))[0]
        # Split the PDF into images with Ghostscript. Create a sub-folder in the
        # OS temp folder to store those images.
        imagesFolder = getOsTempFolder(sub=True)
        device = 'png16m'
        ext = PdfImporter.gsDevices[device]
        dpi = '125'
        cmd = ['gs', '-dSAFER', '-dNOPAUSE', '-dBATCH', '-sDEVICE=%s' % device,
               '-r%s' % dpi, '-dTextAlphaBits=4', '-dGraphicsAlphaBits=4',
               '-sOutputFile=%s/%s%%d.%s' % (imagesFolder, imagePrefix, ext),
               self.importPath]
        utils.executeCommand(cmd)
        # Check that at least one image was generated
        succeeded = False
        firstImage = '%s1.%s' % (imagePrefix, ext)
        for fileName in os.listdir(imagesFolder):
            if fileName == firstImage:
                succeeded = True
                break
        if not succeeded: raise PodError(PDF_TO_IMG_ERROR)
        # Insert images into the result
        noMoreImages = False
        i = 0
        while not noMoreImages:
            i += 1
            nextImage = '%s/%s%d.%s' % (imagesFolder, imagePrefix, i, ext)
            if os.path.exists(nextImage):
                # Use internally an Image importer for doing this job
                imgImporter = ImageImporter(None, nextImage, ext, self.renderer)
                imgImporter.init('paragraph',True,None,None,None,True,None)
                self.res += imgImporter.run()
                os.remove(nextImage)
            else:
                noMoreImages = True
        os.rmdir(imagesFolder)
        return self.res

    # Other useful gs commands -------------------------------------------------
    # Convert a PDF from colored to grayscale
    #gs -sOutputFile=grayscale.pdf -sDEVICE=pdfwrite
    #   -sColorConversionStrategy=Gray -dProcessColorModel=/DeviceGray
    #   -dCompatibilityLevel=1.4 -dNOPAUSE -dBATCH colored.pdf
    # Downsample inner images to produce a smaller PDF
    #gs -sOutputFile=smaller.pdf -sDEVICE=pdfwrite
    #   -dCompatibilityLevel=1.4 -dPDFSETTINGS=/screen
    #   -dNOPAUSE -dBATCH some.pdf
    # The "-dPDFSETTINGS=/screen is a shorthand for:
    #-dDownsampleColorImages=true \
    #-dDownsampleGrayImages=true \
    #-dDownsampleMonoImages=true \
    #-dColorImageResolution=72 \
    #-dGrayImageResolution=72 \
    #-dMonoImageResolution=72

class ConvertImporter(DocImporter):
    '''This class allows to import the content of any file that LibreOffice (LO)
       can convert into PDF: doc, rtf, xls. It first calls LO to convert the
       document into PDF, then calls a PdfImporter.'''
    def run(self):
        # This feature is only available in the open source version
        if utils.commercial: raise utils.CommercialError()
        # Convert the document into PDF with LibreOffice
        output = self.renderer.callLibreOffice(self.importPath, 'pdf')
        if output: raise PodError(TO_PDF_ERROR % output)
        pdfFile = '%s.pdf' % os.path.splitext(self.importPath)[0]
        # Launch a PdfImporter to import this PDF into the POD result
        pdfImporter = PdfImporter(None, pdfFile, 'pdf', self.renderer)
        return pdfImporter.run()

# ------------------------------------------------------------------------------
class Image:
    '''Represents an image on disk. This class is used to detect the image type
       and size.'''
    jpgTypes = ('jpg', 'jpeg')

    def __init__(self, path, format):
        self.path = path # The image absolute path on disk
        self.format = format
        # Determine image size in pixels (again, by reading its first bytes)
        self.width, self.height = self.getSizeInPx()

    def getSizeInPx(self):
        '''Reads the first bytes from the image on disk to get its size'''
        x = y = None
        # Get the file format from the file name of absent
        format = self.format or os.path.splitext(self.path)[1][1:]
        # Read the file on disk
        f = open(self.path, 'rb')
        if format in Image.jpgTypes:
            # Dummy read to skip header ID
            f.read(2)
            while True:
                # Extract the segment header
                marker, code, length = struct.unpack("!BBH", f.read(4))
                # Verify that it's a valid segment
                if marker != 0xFF:
                    # No JPEG marker
                    break
                elif code >= 0xC0 and code <= 0xC3:
                    # Segments that contain size info
                    y, x = struct.unpack("!xHH", f.read(5))
                    break
                else:
                    # Dummy read to skip over data
                    f.read(length-2)
        elif format == 'png':
            # Dummy read to skip header data
            f.read(12)
            if f.read(4) == "IHDR":
                x, y = struct.unpack("!LL", f.read(8))
        elif format == 'gif':
            imgType = f.read(6)
            buf = f.read(5)
            if len(buf) == 5:
                # else: invalid/corrupted GIF (bad header)
                x, y, u = struct.unpack("<HHB", buf)
        f.close()
        if x and y:
            return float(x)/px2cm, float(y)/px2cm
        else:
            return x, y

# Compute size of images -------------------------------------------------------
class ImageImporter(DocImporter):
    '''This class allows to import into the ODT result an image stored
       externally.'''
    anchorTypes = ('page', 'paragraph', 'char', 'as-char')
    WRONG_ANCHOR = 'Wrong anchor. Valid values for anchors are: %s.'
    pictFolder = '%sPictures%s' % (os.sep, os.sep)
    # Path of a replacement image, to use when the image to import is not found
    imageNotFound = os.path.join(os.path.dirname(appy.pod.__file__),
                                 'imageNotFound.jpg')

    def getZopeImage(self, at):
        '''Gets the Zope Image via an image resolver'''
        resolver = self.renderer.imageResolver
        if not resolver or not at.startswith(resolver.absolute_url()): return
        # The resolver is a Zope application or a sub-object within it. From it,
        # we will retrieve the object on which the image is stored and get the
        # file to download.
        urlParts = urllib.parse.urlsplit(at)
        path = urlParts[2][1:].split('/')
        image = None
        try:
            image = resolver.unrestrictedTraverse(path)
        except (KeyError, AttributeError):
            # Maybe a rewrite rule as added some prefix to all URLs ?
            try:
                path = path[1:]
                # Make sure we still have a path, or it gets the resolver
                if path:
                    image = resolver.unrestrictedTraverse(path)
            except (KeyError, AttributeError):
                pass # The image was not found
        return image

    def checkAt(self, at):
        '''Do not raise an exception when p_at does not correspond to an
           existing file. We will dump a replacement image instead.'''
        at = DocImporter.checkAt(self, at, raiseOnError=False)
        if at.startswith('http'):
            # Try to get the image
            try:
                response = Resource(at).get(followRedirect=False)
            except Resource.Error:
                response = None # Can't get the distant image
            if response and (response.code == 200):
                # Remember the response
                self.httpResponse = response
                return at
            # The HTTP GET did not work, maybe for security reasons (we probably
            # have no permission to get the file). But maybe the URL was a local
            # one, from an application server running this POD code. In this
            # case, if an image resolver has been given to POD, use it to
            # retrieve the image.
            self.zopeImage = self.getZopeImage(at)
            if self.zopeImage:
                return at
            # We could not find the image
            self.format = 'jpg'
            at = self.imageNotFound
        else:
            if not os.path.isfile(at):
                self.format = 'jpg'
                at = self.imageNotFound
            elif self.format == 'image':
                # Read its format by reading its first bytes
                self.format = imghdr.what(str(at))
        return at

    def getImportFolder(self):
        return os.path.join(self.tempFolder, 'unzip', 'Pictures')

    def moveFile(self):
        '''Copies file at self.at into the ODT file at self.importPath'''
        at = self.at
        importPath = self.importPath
        # Has this image already been imported ?
        for imagePath, imageAt in self.fileNames.items():
            if imageAt == at: # Yes
                i = importPath.rfind(self.pictFolder) + 1
                return importPath[:i] + imagePath
        # The image has not already been imported: copy it
        if not at.startswith('http'):
            shutil.copy(at, importPath)
            # Ensure we can modify the image (with imagemagick)
            os.chmod(importPath, stat.S_IREAD | stat.S_IWRITE)
            return importPath
        # The image has (maybe) been retrieved from a HTTP GET
        response = getattr(self, 'httpResponse', None)
        if response:
            # Retrieve the image format
            format = response.headers['Content-Type']
            if format in utils.mimeTypesExts:
                # At last, I can get the file format
                self.format = utils.mimeTypesExts[format]
                importPath += self.format
                f = open(importPath, 'wb')
                f.write(response.body)
                f.close()
                return importPath
        # The image has (maybe) been retrieved from Zope
        zopeImage = getattr(self, 'zopeImage', None)
        if zopeImage:
            blobWrapper = zopeImage.getBlobWrapper()
            self.format = utils.mimeTypesExts[blobWrapper.content_type]
            importPath += self.format
            blob = blobWrapper.getBlob()
            # If we do not check 'readers', the blob._p_blob_committed is
            # sometimes None.
            blob.readers
            blobPath = blob._p_blob_committed
            shutil.copy(blobPath, importPath)
            return importPath

    def init(self, anchor, wrapInPara, size, sizeUnit, cssAttrs, keepRatio,
             convertOptions):
        '''ImageImporter-specific constructor'''
        # Initialise anchor
        if anchor not in self.anchorTypes:
            raise PodError(self.WRONG_ANCHOR % str(self.anchorTypes))
        self.anchor = anchor
        self.wrapInPara = wrapInPara
        self.size = size
        self.sizeUnit = sizeUnit
        self.keepRatio = keepRatio
        self.convertOptions = convertOptions
        # CSS attributes
        self.cssAttrs = cssAttrs
        if cssAttrs:
            w = getattr(self.cssAttrs, 'width', None)
            h = getattr(self.cssAttrs, 'height', None)
            if w and h:
                self.sizeUnit = w.unit
                self.size = (w.value, h.value)
        # Call imagemagick to perform a custom conversion if required
        options = self.convertOptions
        image = None
        transformed = False
        if options:
            # This feature is only available in the open source version
            if utils.commercial: raise utils.CommercialError()
            if callable(options): # It is a function
                image = Image(self.importPath, self.format)
                options = self.convertOptions(image)
            if options:
                # Ensure we have the right to modify the file@self.importPath
                cmd = ['convert', self.importPath] + options.split() + \
                      [self.importPath]
                out, err = utils.executeCommand(cmd)
                if err: raise Exception(CONVERT_ERROR)
                transformed = True
        # Avoid creating an Image instance twice if no transformation occurred
        if image and not transformed:
            self.image = image
        else:
            self.image = Image(self.importPath, self.format)

    def getImageSize(self):
        '''Get or compute the image size and returns the corresponding ODF
           attributes specifying image width and height expressed in cm.'''
        # Compute image size, in cm
        width, height = self.image.width, self.image.height
        if self.size:
            # Apply a percentage when self.sizeUnit is 'pc'
            if self.sizeUnit == 'pc':
                # If width or height could not be computed, it is impossible
                if not width or not height: return ''
                if self.keepRatio:
                    ratioW = ratioH = float(self.size[0]) / 100
                else:
                    ratioW = float(self.size[0]) / 100
                    ratioH = float(self.size[1]) / 100
                width = width * ratioW
                height = height * ratioH
            else:
                # Get, from self.size, required width and height, and convert
                # it to cm when relevant.
                w, h = self.size
                if self.sizeUnit == 'px':
                    w = float(w) / px2cm
                    h = float(h) / px2cm
                # Use (w, h) as is if we don't care about keeping image ratio or
                # if we couldn't determine image's width or height.
                if (not width or not height) or not self.keepRatio:
                    width, height = w, h
                else:
                    # Compute height and width ratios and apply the minimum
                    # ratio to both width and height.
                    ratio = min(w/width, h/height)
                    width = width * ratio
                    height = height * ratio
        # Return the ODF attributes
        if not width or not height: return ''
        s = self.svgNs
        return ' %s:width="%fcm" %s:height="%fcm"' % (s, width, s, height)

    def run(self):
        # Some shorcuts for the used xml namespaces
        d = self.drawNs
        t = self.textNs
        x = self.linkNs
        # Compute path to image
        i = self.importPath.rfind(self.pictFolder)
        imagePath = self.importPath[i+1:].replace('\\', '/')
        self.fileNames[imagePath] = self.at
        # In the case of SVG files, perform an image conversion to PNG
        if imagePath.endswith('.svg'):
            newImportPath = os.path.splitext(self.importPath)[0] + '.png'
            out, err = utils.executeCommand(['convert', self.importPath,
                                            newImportPath])
            if err: raise Exception(CONVERT_ERROR)
            os.remove(self.importPath)
            self.importPath = newImportPath
            imagePath = os.path.splitext(imagePath)[0] + '.png'
            self.format = 'png'
        # Compute image alignment if CSS attr "float" is specified
        floatValue = getattr(self.cssAttrs, 'float', None)
        if floatValue:
            floatValue = floatValue.value.capitalize()
            styleInfo = '%s:style-name="podImage%s" ' % (d, floatValue)
            self.anchor = 'char'
        else:
            styleInfo = ''
        image = '<%s:frame %s%s:name="%s" %s:z-index="0" ' \
                '%s:anchor-type="%s"%s><%s:image %s:type="simple" ' \
                '%s:show="embed" %s:href="%s" %s:actuate="onLoad"/>' \
                '</%s:frame>' % (d, styleInfo, d, getUuid(), d, t, self.anchor,
                self.getImageSize(), d, x, x, x, imagePath, x, d)
        if hasattr(self, 'wrapInPara') and self.wrapInPara:
            style = isinstance(self.wrapInPara, str) and \
                    (' text:style-name="%s"' % self.wrapInPara) or ''
            image = '<%s:p%s>%s</%s:p>' % (t, style, image, t)
        self.res += image
        return self.res
# ------------------------------------------------------------------------------

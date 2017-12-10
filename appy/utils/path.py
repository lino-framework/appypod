'''Operations on files and folders (=paths)'''

# ------------------------------------------------------------------------------
import os, os.path, shutil

# ------------------------------------------------------------------------------
class FolderDeleter:
    @staticmethod
    def delete(dirName):
        '''Recursively deletes p_dirName.'''
        dirName = os.path.abspath(dirName)
        for root, dirs, files in os.walk(dirName, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(dirName)

    @staticmethod
    def deleteEmpty(dirName):
        '''Deletes p_dirName and its parent dirs if they are empty.'''
        while True:
            try:
                if not os.listdir(dirName):
                    os.rmdir(dirName)
                    dirName = os.path.dirname(dirName)
                else:
                    break
            except OSError:
                break

# ------------------------------------------------------------------------------
extsToClean = ('.pyc', '.pyo', '.fsz', '.deltafsz', '.dat', '.log')
def cleanFolder(folder, exts=extsToClean, folders=(), verbose=False):
    '''This function allows to remove, in p_folder and subfolders, any file
       whose extension is in p_exts, and any folder whose name is in
       p_folders.'''
    if verbose: print('Cleaning folder %s...' % folder)
    # Remove files with an extension listed in p_exts
    if exts:
        for root, dirs, files in os.walk(folder):
            for fileName in files:
                ext = os.path.splitext(fileName)[1]
                if (ext in exts) or ext.endswith('~'):
                    fileToRemove = os.path.join(root, fileName)
                    if verbose: print('Removing file %s...' % fileToRemove)
                    os.remove(fileToRemove)
    # Remove folders whose names are in p_folders.
    if folders:
        for root, dirs, files in os.walk(folder):
            for folderName in dirs:
                if folderName in folders:
                    toDelete = os.path.join(root, folderName)
                    if verbose: print('Removing folder %s...' % toDelete)
                    FolderDeleter.delete(toDelete)

# ------------------------------------------------------------------------------
def resolvePath(path):
    '''p_path is a file path that can contain occurences of "." and "..". This
       function resolves them and procuces a minimal path.'''
    res = []
    for elem in path.split(os.sep):
        if elem == '.': pass
        elif elem == '..': res.pop()
        else: res.append(elem)
    return os.sep.join(res)

# ------------------------------------------------------------------------------
def copyFolder(source, dest, cleanDest=False):
    '''Copies the content of folder p_source to folder p_dest. p_dest is
       created, with intermediary subfolders if required. If p_cleanDest is
       True, it removes completely p_dest if it existed. Else, content of
       p_source will be added to possibly existing content in p_dest, excepted
       if file names corresponds. In this case, file in p_source will overwrite
       file in p_dest.'''
    dest = os.path.abspath(dest)
    # Delete the dest folder if required
    if os.path.exists(dest) and cleanDest:
        FolderDeleter.delete(dest)
    # Create the dest folder if it does not exist
    if not os.path.exists(dest):
        os.makedirs(dest)
    # Copy the content of p_source to p_dest.
    for name in os.listdir(source):
        sourceName = os.path.join(source, name)
        destName = os.path.join(dest, name)
        if os.path.isfile(sourceName):
            # Copy a single file
            shutil.copy(sourceName, destName)
        elif os.path.isdir(sourceName):
            # Copy a subfolder (recursively)
            copyFolder(sourceName, destName)

# ------------------------------------------------------------------------------
def getOsTempFolder(sub=False):
    '''Gets the absolute path to the temp folder on this machine. If p_sub is
       True, it creates a sub-folder within this temp folder and returns its
       absolute path instead of the "root" temp folder path.'''
    tmp = '/tmp'
    if os.path.exists(tmp) and os.path.isdir(tmp):
        res = tmp
    elif 'TMP' in os.environ:
        res = os.environ['TMP']
    elif 'TEMP' in os.environ:
        res = os.environ['TEMP']
    else:
        raise Exception("Sorry, I can't find a temp folder on your machine.")
    if sub:
        subFolder = os.path.join(res, 'Appy%f' % time.time())
        os.mkdir(subFolder)
        res = subFolder
    return res

# ------------------------------------------------------------------------------
def getTempFileName(prefix='', extension='', timestamp=True):
    '''Returns the absolute path to a unique file name in the OS temp folder.
       The caller will then be able to create a file with this name.

       A p_prefix to this file can be provided. If an p_extension is provided,
       it will be appended to the name. Both dotted and not dotted versions
       of p_extension are allowed (ie, ".pdf" or "pdf").'''
    # Suffix the file name with a timestamp when relevant
    suffix = timestamp and ('_%f' % time.time()) or ''
    res = os.path.join(getOsTempFolder(), '%s%s' % (prefix, suffix))
    if extension:
        if extension.startswith('.'): res += extension
        else: res += '.' + extension
    return res

# ------------------------------------------------------------------------------
class UnmarshalledFile:
    '''Used for producing file objects from a marshalled Python object.'''
    def __init__(self):
        self.name = '' # The name of the file on disk
        self.mimeType = None # The MIME type of the file
        self.content = '' # The binary content of the file or a file object
        self.size = 0 # The length of the file in bytes.
# ------------------------------------------------------------------------------

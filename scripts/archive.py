import os, tarfile, zipfile, tempfile

class Archive:
	def __init__(self):
		self.impl = None

	def extractall(self, dir): return self.impl.extractall(dir)
	def close(self): return self.impl.close()

class Tar(Archive):
	def __init__(self, path, mode = 'r'):
		Archive.__init__(self)
		self.impl = tarfile.open(path, mode)
	def add(self, path, arcname): self.impl.add(path, arcname)
	def write(self, content, arcname):
		with tempfile.TemporaryFile() as io:
			io.write(content)
			info = tarfile.TarInfo(arcname)
			info.size = io.tell()
			info.type = tarfile.REGTYPE
			io.seek(0)
			self.impl.addfile(info, io)

class Zip(Archive):
	def __init__(self, path, mode = 'r'):
		Archive.__init__(self)
		self.impl = zipfile.ZipFile(path, mode)
	def add(self, path, arcname): self.impl.write(path, arcname)
	def write(self, content, arcname): self.impl.writestr(arcname, content)

known_exts = [
	(["tar.gz", "tgz"], "w:gz"),
	(["tar.bz2", "tbz", "tbz2", "tb2"], "w:bz2"),
	(["zip"], "w")
]

def open(name, mode = 'r'):
	if mode[:1] == 'r':
		if tarfile.is_tarfile(name):
			return Tar(name)
		elif zipfile.is_zipfile(name):
			return Zip(name)
		return None

	if mode[:1] == 'w':
		for known_ext in known_exts:
			for ext in known_ext[0]:
				if name.endswith('.' + ext):
					opts = known_ext[1]
					break
			if opts is not None: break
		if opts is None: return None
		try: os.makedirs(os.path.dirname(name))
		except: pass
		if ':' in opts:
			return Tar(name, opts)
		return Zip(name, opts)

	return None

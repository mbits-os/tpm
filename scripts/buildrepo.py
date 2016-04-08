import os, sys, archive, recipe
from xml.sax.saxutils import escape

class RepoPkg:
	def __init__(self, uri, props):
		self.uri = uri
		self.id = props['id']
		self.name = props['name']
		self.version = props['version']
		self.platform = props['platform']
		self.requires = props['requires']
		self.provides = props['provides']

	def xml(self, out):
		out.write('  <package\n')
		out.write('    id="{}"\n'.format(escape(self.id)))
		out.write('    pkg="{}"\n'.format(escape(self.uri)))
		out.write('    name="{}"\n'.format(escape(self.name)))
		out.write('    version="{}"\n'.format(escape(self.version)))
		out.write('    platform="{}">\n'.format(escape(self.platform)))
		for name in self.provides:
			out.write('    <provides name="{}"/>\n'.format(escape(name)))
		for name in self.requires:
			out.write('    <requires name="{}"/>\n'.format(escape(name)))
		out.write('  </package>\n')

class PlatformRepo:
	def __init__(self):
		self.packages = []
		self.provides = {}
		self.requires = {}

	def append(self, pkg):
		self.packages.append(pkg)

	def repopulate(self):
		self.provides = {}
		self.requires = {}
		for pkg in self.packages:
			for name in pkg.provides:
				if name not in self.provides:
					self.provides[name] = []
				self.provides[name].append(pkg)

			for name in pkg.requires:
				if name not in self.requires:
					self.requires[name] = []
				self.requires[name].append(pkg)

	def minimize(self):
		for req in self.requires:
			if req in self.provides:
				del self.requires[req]
		if not len(self.requires):
			return True
		for req in self.requires:
			missing = self.requires[req]
			for pkg in missing:
				sys.stdout.write('%s: warning: repo cannot supply package for \'%s\' requirement\n' % (pkg.uri, req))
				self.packages.remove(pkg)
		return True

class Repo:
	def __init__(self):
		self.platforms = {}

	def append(self, pkg):
		if pkg.platform not in self.platforms:
			self.platforms[pkg.platform] = PlatformRepo()
		self.platforms[pkg.platform].append(pkg)

	def repopulate(self):
		for platform in self.platforms:
			self.platforms[platform].repopulate()

	def minimize(self):
		result = True
		removed = []
		for platform in self.platforms:
			result &= self.platforms[platform].minimize()
			if not len(self.platforms[platform].packages):
				removed.append(platform)
		for platform in removed:
			del self.platforms[platform]
		return result

platforms = []
base = 'packages'
repo = Repo()

for root, dirs, files in os.walk(base):
	platforms = [os.path.join(root, dir) for dir in dirs]
	break

packages = []
for platform in platforms:
	for root, dirs, files in os.walk(platform):
		packages += [os.path.join(root, file) for file in files]
		break

for pkg in packages:
	arc = archive.open(pkg)
	if arc is None: continue
	try:
		manifest = arc.read('MANIFEST')
		if manifest is None: continue
		manifest = 	recipe.parse_manifset(manifest)
	finally: arc.close()

	pkg = RepoPkg(os.path.relpath(pkg, base), manifest)
	repo.append(pkg)

repo.repopulate()
while not repo.minimize():
	repo.repopulate()

reorg = {}
for platform in repo.platforms:
	p = repo.platforms[platform]
	for pkg in p.packages:
		key = (pkg.name, pkg.version)
		if key not in reorg:
			reorg[key] = {}
		reorg[key][pkg.uri] = pkg

repo = []
for key in sorted(reorg):
	for uri in sorted(reorg[key]):
		repo.append(reorg[key][uri])

def xml(repo, out):
	out.write('<?xml version="1.0" encoding="utf-8"?>\n<repo>\n')
	for pkg in repo:
		pkg.xml(out)
	out.write('</repo>\n')

# in case there are no no packages yet:
try: os.mkdir('packages')
except: pass

with open('packages/repo.xml', 'w') as out:
	xml(repo, out)
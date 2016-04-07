import os, sys, subprocess, glob, wget, archive, hashlib, recipe

try:
	result = recipe.parse_recipe(sys.argv[1])
except SyntaxError as se:
	sys.stderr.write(se.pretty())
	sys.stderr.write('\n')
	exit(1)

def mkdir(path):
	if os.path.exists(path): return
	sys.stdout.write('+ mkdir -p {}\n'.format(path))
	os.makedirs(path)

def rm(path):
	if not os.path.exists(path): return
	if os.path.isdir(path):
		sys.stdout.write('+ rm -r {}\n'.format(path))
		os.removedirs(path)
		return

	sys.stdout.write('+ rm {}\n'.format(path))
	os.remove(path)

def cd(path):
	sys.stdout.write('+ cd {}\n'.format(path))
	os.chdir(path)

def bar_none(current, total, width=80): return ''

sys.stdout.write('=' * 80 + '\n')

if 'upstream' not in result.props:
	sys.stderr.write('{0}: `Upstream` url is missing from the recipe'.format(sys.argv[1]))
	exit(1)

stage = os.path.join('stage', result.props['dir'], os.path.basename(sys.argv[1]))

root = os.getcwd()
mkdir(stage)
cd(stage)

mkdir(result.props['build_dir'])
mkdir(result.props['prefix'])
mkdir(result.props['sources'])

sys.stdout.write('+ wget {}\n'.format(result.props['upstream']))
filename = wget.download(result.props['upstream'], bar=bar_none)

arc = archive.open(filename)
if arc is None:
	sys.stderr.write('{0}: do not know how to unpack {1}'.format(sys.argv[1], filename))
	exit(1)

if isinstance(arc, archive.Tar):
	sys.stdout.write('+ tar -x {}\n'.format(filename))
elif isinstance(arc, archive.Zip):
	sys.stdout.write('+ unzip {}\n'.format(filename))


try:
	arc.extractall(result.props['sources'])
finally:
	arc.close()

rm(filename)

def call(cmd):
	sys.stdout.write('++ {0}\n'.format(" ".join([recipe.escape(arg) for arg in cmd])))
	if cmd[0] == 'cd':
		try: os.chdir(cmd[1])
		except Exception as e:
			print (e)
			return 1
		return 0
	return subprocess.call(cmd)

sys.stdout.write('+ build recipe\n')
for cmd in result.build:
	retval = call(cmd)
	if retval:
		sys.stdout.write('error in sub-process\n')
		exit(retval)

cd(root)

for pkg in result.packages:
	name = os.path.join('packages', pkg.name)
	sys.stdout.write('+ packing {}\n'.format(name))
	arc = archive.open(name, 'w')
	if arc is None:
		sys.stdout.write('{0}: do not know how to pack {1}'.format(sys.argv[1], name))
		exit(1)

	hash = hashlib.sha256()
	base = os.path.join(stage, result.props['prefix'])
	for file in pkg.files:
		match = os.path.join(base, file)
		for path in glob.iglob(match):
			dest = os.path.join('files', os.path.relpath(path, base)).replace('\\', '/')
			arc.add(path, dest)
			with open(path, 'rb') as f:
				hash.update(f.read())

	manifest = u''
	if 'name' in pkg.props:
		manifest += u'Name: {}\n'.format(pkg.props['name'])
	elif 'name' in result.props:
		manifest += u'Name: {}\n'.format(result.props['name'])

	if 'version' in pkg.props:
		manifest += u'Version: {}\n'.format(pkg.props['version'])
	elif 'version' in result.props:
		manifest += u'Version: {}\n'.format(result.props['version'])

	if 'dir' in result.props:
		manifest += u'Platform: {}\n'.format(result.props['dir'].upper())

	for name in pkg.provides:
		manifest += u'Provides: {}\n'.format(recipe.escape(name))

	for name in pkg.requires:
		manifest += u'Requires: {}\n'.format(recipe.escape(name))

	hash.update(manifest.encode('utf-8'))
	manifest = u'Id: {}\n'.format(hash.hexdigest()) + manifest

	arc.write(manifest.encode('utf-8'), 'MANIFEST')
	arc.close()

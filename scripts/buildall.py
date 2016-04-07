import os, sys, recipe
from subprocess import check_call

pkgs = {}
for root, dir, files in os.walk('recipes'):
	for filename in files:
		pkgs[os.path.join(root, filename)] = []

remove = []
for conf in pkgs:
	try: result = recipe.parse_recipe(conf)
	except recipe.SyntaxError as se:
		sys.stderr.write(se.pretty())
		sys.stderr.write('\n')
		remove.append(conf)
		continue
	except:
		remove.append(conf)
		continue
	pkgs[conf] = [os.path.join('packages', pkg.name) for pkg in result.packages]

for conf in remove:
	del pkgs[conf]

def mtime(path):
	if not os.path.exists(path): return 0
	return os.stat(path).st_mtime

confs = []
for conf in sorted(pkgs):
	needs_update = False
	lhs = mtime(conf)
	for pkg in pkgs[conf]:
		rhs = mtime(pkg)
		if rhs < lhs:
			needs_update = True
			break
	if needs_update:
		confs.append(conf)

for conf in confs:
	for pkg in pkgs[conf]:
		sys.stderr.write('{}\n'.format(pkg))
	result = check_call(['python', 'scripts/build.py', conf])
	if result: exit(result)

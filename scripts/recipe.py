import os, sys, re, shlex
from collections import namedtuple

TEXT = 0
CALL = 1
VARIABLE = 2
PREPROC = 3

Preproc = namedtuple('Preproc', ['pos', 'kw', 'value'])
Call = namedtuple('Call', ['pos', 'name', 'value'])
Variable = namedtuple('Variable', ['pos', 'name', 'value'])
Text = namedtuple('Text', ['pos', 'text'])

class Tokenizer:
	varname = re.compile('^([a-zA-Z_][a-zA-Z0-9_]*)(.*)$')
	def __init__(self):
		self.preproc = re.compile('^\%([a-zA-Z_][a-zA-Z0-9_]*)\s*(.*)$')
		self.cmd = re.compile('^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*)$')
		self.var = re.compile('^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.*)$')
		self.line = 0
		self.text = ''

	def next_line(self, line):
		line = line.split('#', 1)[0].strip()

		self.line += 1
		self.text += line

		l = len(self.text)
		if l and self.text[l - 1] == '\\':
			self.text = self.text[:l - 1]
			return

		line = self.text
		self.text = ''

		if line == '': return
		m = self.preproc.match(line)
		if m:
			val = m.group(2)
			if val == '':
				yield Preproc(self.line, m.group(1), None)
			else:
				yield Preproc(self.line, m.group(1), m.group(2))
			return
		m = self.cmd.match(line)
		if m:
			yield Call(self.line, m.group(1), m.group(2))
			return
		m = self.var.match(line)
		if m:
			yield Variable(self.line, m.group(1), m.group(2))
			return
		yield Text(self.line, line)

def is_unix():
	return os.name == 'posix'

def is_windows():
	return os.name == 'nt'

def is_apple():
	return sys.platform.startswith('darwin')

class SyntaxError:
	def __init__(self, path, line, message, embed):
		self.path = path
		self.line = line
		self.message = message
		self.embed = embed

	def pretty(self, kind = 'error'):
		txt = ''
		if self.embed: txt = '\n' + self.embed.pretty('note')
		if is_windows():
			return '{0}({1}): {2}: {3}'.format(self.path, self.line, kind, self.message) + txt
		return '{0}:{1}: {2}: {3}'.format(self.path, self.line, kind, self.message) + txt

class Package:
	def __init__(self, name):
		self.name = name
		self.props = {}
		self.requires = []
		self.provides = []
		self.files = []

class If:
	def __init__(self, pos, name, is_active):
		self.pos = pos
		self.name = name
		self.active = is_active
		self.else_pos = -1
		self.fired = is_active

	def is_active(self):
		return self.active

	def on_elif(self, is_activating):
		if self.else_pos != -1: return False
		if self.fired:
			self.active = False
		else:
			self.active = is_activating
			self.fired = is_activating
		return True

	def on_else(self, pos):
		self.else_pos = pos
		if self.fired:
			self.active = False
		else:
			self.active = True
			self.fired = True

	def sub_if(self, pos, name, is_active):
		sub = If(pos, name, is_active)
		if not self.is_active():
			sub.fired = True
			sub.active = False
		return sub

	def __str__(self):
		_active = 'not '
		_fired = 'not '
		_else = ''
		if self.active: _active = ''
		if self.fired: _fired = 'already '
		if self.else_pos != -1: _else = ', else:{0}'.format(str(self.else_pos))
		return '{0}:{1}, {2}active, {3}fired{4}'.format(str(self.pos), self.name, _active, _fired, _else)

def do_escape(arg):
	return '"' + arg.replace('\\', '\\\\').replace('!','\!') + '"'

def escape(arg):
	if arg == "": return '""'
	if '\\' in arg: return do_escape(arg)
	if '\n' in arg: return do_escape(arg)
	for c in arg:
		if c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789,._+:@%/-=':
			return do_escape(arg)
	return arg

class Recipe:
	def __init__(self, props, build, packages):
		self.props = props
		self.build = build
		self.packages = packages

	def info(recipe, out):
		out.write('PROPERTIES:\n')
		for prop in sorted(recipe.props):
			out.write('  {0}: {1}\n'.format(prop, recipe.props[prop]))

		out.write('\nBUILD:\n')
		for cmd in recipe.build:
			out.write('  {0}\n'.format(" ".join([escape(arg) for arg in cmd])))

		for pkg in recipe.packages:
			out.write('\nPKG {0}\n'.format(pkg.name))
			if len(pkg.props):
				out.write('  PROPS:\n')
				for name in sorted(pkg.props):
					out.write('    {0}: {1}\n'.format(name, pkg.props[name]))
			if len(pkg.requires):
				out.write('  REQ:\n')
				for name in pkg.requires:
					out.write('    {0}\n'.format(name))
			if len(pkg.provides):
				out.write('  PROV:\n')
				for name in pkg.provides:
					out.write('    {0}\n'.format(name))
			if len(pkg.files):
				out.write('  PACK:\n')
				for name in pkg.files:
					out.write('    {0}\n'.format(name))

class RecipeBuilder:
	def __init__(self, path):
		self.path = path
		self.macros = {}
		self.vars = {}
		self.props = {}
		self.packages = []
		self.package = None
		self.commands = []
		self.building = -1
		self.ifstack = []

		self.vars['cmake'] = 'cmake'
		if is_unix():
			self.dir = 'posix'
			self.vars['mkdir'] = 'mkdir -p'
			self.macros['UNIX'] = 1

		if is_windows():
			self.dir = 'windows'
			self.vars['mkdir'] = 'python "{0}"'.format(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mkdir.py'))
			self.macros['WIN32'] = 1

		if is_apple():
			self.dir = 'darwin'
			self.vars['cmake'] = '/Applications/CMake.app/Contents/bin/cmake'
			self.macros['APPLE'] = 1

		self.props['dir'] = self.dir
		self.props['build_dir'] = 'build.dir'
		self.props['prefix'] = 'output'
		self.props['sources'] = 'source'

	def mkerror(self, message, embed = None, pos = -1):
		if pos < 1: pos = self.pos
		return SyntaxError(self.path, pos, message, embed)

	def throw(self, message, embed = None):
		raise self.mkerror(message, embed)

	def is_active(self):
		l = len(self.ifstack)
		if not l: return True
		return self.ifstack[l - 1].is_active()

	def use(self, tok):
		self.pos = tok.pos
		if isinstance(tok, Preproc):
			if tok.kw in RecipeBuilder.preproc:
				RecipeBuilder.preproc[tok.kw](self, tok.value)
			else:
				self.throw('Unknown preprocessor directive %{0}'.format(tok.kw))

		elif self.building != -1:
			if isinstance(tok, Text):
				if self.is_active():
					self.commands.append(self.split(tok.text))
			else:
				self.throw('Expecting %endbuild or command')

		elif not self.is_active():
			return

		elif isinstance(tok, Call):
			if tok.name in RecipeBuilder.calls:
				RecipeBuilder.calls[tok.name](self, tok.value)
			elif tok.name in RecipeBuilder.props:
				kw = tok.name.lower()
				val = self.expand(tok.value)
				if not self.package:
					self.props[kw] = val
				else:
					if kw not in self.props:
						self.props[kw] = val
					self.package.props[kw] = val
			else:
				self.throw('Unknown instruction: {0}'.format(tok.name))

		elif isinstance(tok, Variable):
			self.vars[tok.name] = self.expand(tok.value)

	def on_build(self, value):
		if self.building != -1:
			self.throw('embedded %build', self.mkerror('see original %build', pos=self.building))
		self.building = self.pos

	def on_endbuild(self, value):
		if self.building == -1:
			self.throw('expecting %build')
		self.building = -1

	def on_define(self, value):
		self.macros[value] = 1

	def if_eval(self, value):
		if value in self.macros:
			return self.macros[value]
		return 0

	def on_if(self, value):
		next = None
		active = self.if_eval(value)
		if len(self.ifstack):
			next = self.ifstack[len(self.ifstack) - 1].sub_if(self.pos, value, active)
		else:
			next = If(self.pos, value, active)
		self.ifstack.append(next)

	def on_elif(self, value):
		last = len(self.ifstack)
		if last == 0:
			self.throw('%elif without %if')
		last -= 1
		if not self.ifstack[last].on_elif(self.if_eval(value)):
			self.throw('%elif after %else', self.mkerror('see %else', pos=self.ifstack[last].else_pos))

	def on_else(self, value):
		last = len(self.ifstack)
		if last == 0:
			self.throw('%else without %if')
		last -= 1
		self.ifstack[last].on_else(self.pos)

	def on_endif(self, value):
		if len(self.ifstack) == 0:
			self.throw('%endif without %if')
		self.ifstack = self.ifstack[:len(self.ifstack) - 1]

	def on_package(self, value):
		if self.package is not None:
			self.packages.append(self.package)
		self.package = Package(os.path.join(self.dir, self.split(value)[0]))

	def pack(self, files):
		if self.package is None:
			self.throw('Expecting %package')
		self.package.files.extend(self.split(files))

	def requires(self, dependencies):
		if self.package is None:
			self.throw('Expecting %package')
		self.package.requires.extend(self.split(dependencies))

	def provides(self, dependencies):
		if self.package is None:
			self.throw('Expecting %package')
		self.package.provides.extend(self.split(dependencies))

	def expand(self, value):
		if '$' not in value:
			return value

		value = value.split('$')
		out = value[0]
		value = value[1:]
		for t in value:
			if t == '':
				continue
			if t[0] == '{':
				t = t[1:].split('}', 1)
				out += self.getvalue(t[0]) + t[1]
				continue
			m = Tokenizer.varname.match(t)
			if m:
				out += self.getvalue(m.group(1)) + m.group(2)
		return out

	def getvalue(self, name):
		if name in self.props:
			return self.props[name]
		if name in self.vars:
			return self.vars[name]
		if name in self.macros:
			return self.macros[name]
		sys.stderr.write('{0}\n'.format(self.mkerror('missing value for ${0}'.format(name)).pretty('warning')))
		return '$$$'

	def split(self, value):
		value = shlex.split(self.expand(value))
		return [v.replace('$$$', ' ') for v in value]

	def build(self):
		if self.package is not None:
			self.packages.append(self.package)
		self.package = None
		if self.building != -1:
			if self.building == self.pos:
				self.throw('unfinished %build')
			else:
				self.throw('unfinished %build', self.mkerror('see original %build', pos=self.building))
		if len(self.ifstack) > 0:
			last = len(self.ifstack) - 1
			self.throw('unfinished %if', self.mkerror('see original %if', pos=self.ifstack[last][0]))

		return Recipe(self.props, self.commands, self.packages)

RecipeBuilder.preproc = {
	'build': RecipeBuilder.on_build,
	'endbuild': RecipeBuilder.on_endbuild,
	'define': RecipeBuilder.on_define,
	'if': RecipeBuilder.on_if,
	'elif': RecipeBuilder.on_elif,
	'else': RecipeBuilder.on_else,
	'endif': RecipeBuilder.on_endif,
	'package': RecipeBuilder.on_package,
}

RecipeBuilder.calls = {
	'Pack': RecipeBuilder.pack,
	'Requires': RecipeBuilder.requires,
	'Provides': RecipeBuilder.provides,
}

RecipeBuilder.props = ['Name', 'Version', 'Upstream']

def parse_recipe(path):
	tokens = Tokenizer()
	builder = RecipeBuilder(path)
	with open(path) as f:
		for line in f:
			for tok in tokens.next_line(line):
				builder.use(tok)
	return builder.build()

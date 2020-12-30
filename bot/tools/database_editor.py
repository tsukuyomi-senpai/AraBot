from argparse import ArgumentParser
from copy import deepcopy
from json import dump, load
from math import isclose
from typing import Callable, Iterable, TypeVar

DATABASE_FILE_PATH = "./bot/res/database.json"
TABLE_ITEMS = "items"
TABLE_ITEM_TYPES = "item_types"
TABLE_POOLS = "pools"
DROP_RATE_TOLERANCE = 1e-5
STIGMATA_PARTS = ("T", "M", "B")
STIGMATA_PARTS_FULL = tuple(f"({part})" for part in STIGMATA_PARTS)

_T = TypeVar("_T")
_T2 = TypeVar("_T2")

# TODO LIST
# - for the rates, use the ones from the game and let
#   the database editor/gacha script figure out the
#   real drop rates (rate / 100 / item count -> stigmas are special)
# - changerate command
#   change the rate of a specific item set
#   e.g. --pool ex changerate 0.15 0.07
#   note: it should merge equal sets
# - interactive pool updates
#   it would be nice if the user didn't have to type the whole name of items
#   but could instead use regex matching (eg. "Star Shatterer: Vikrant" -> "vikrant")
#   and in case the input is ambiguous the script should let the user choose one
#   from the list of matching options
# - smarter argparse
#   it sucks when you have to type unnecessary parameters
#   such as the listtables command
class GachaEditor:
	def __init__(self):
		with open(DATABASE_FILE_PATH) as database:
			self._database = load(database)
			self._operations = {
				# generic
				"listtables": self.__list_tables,

				# items
				"additem": self.__additem,
				"finditem": self.__finditem,
				"deleteitem": self.__deleteitem,
				"additemset": self.__additemset,

				# pools
				"addpool": self.__addpool,
				"removepool": self.__removepool,
				"addpoolitem": self.__addpoolitem,
				"removepoolitem": self.__removepoolitem,
				"replacepoolitem": self.__replacepoolitem,
				"showpool": self.__showpool,
				"togglepool": self.__togglepool,
				"clonepool": self.__clonepool
			}

	@staticmethod
	def _aggregate(source: Iterable[_T], seed: _T2, func: Callable[[_T2, _T], _T2]) -> _T2:
		current_value = seed
		for item in source:
			current_value = func(current_value, item)
		return current_value

	def __save_database(self):
		'''Saves the database associated to the editor instance.'''
		with open(DATABASE_FILE_PATH, "w+") as database:
			dump(self._database, database, indent="\t")
		print("The database has been saved successfully.")

	def __get_or_initialize_value(self, dictionary: dict, key: str, default_value: object) -> object:
		'''
		Gets the value associated to the specified ``key`` from the specified ``dictionary``.
		If the key isn't present in the dictionary, it is initialized with the specified ``default_value``.
		'''
		value = dictionary.get(key, None)
		if value is not None:
			return value
		dictionary[key] = value = default_value
		return value

	def __find_ids_by_field(self, table_name: str, field_name: str, field_value: str, is_exact: bool = True):
		'''
		Finds all the identifiers in the table with the specified ``table_name``
		whose fields identified by the specified ``field_name``
		match the specified ``field_value``.
		If ``is_exact`` is set to ``True``, only exact matches are returned.
		'''
		predicate = (lambda text: text == field_value) if is_exact else (lambda text: field_value.lower() in text.lower())
		for key, item in self.__get_or_initialize_value(self._database, table_name, {}).items():
			if predicate(item.get(field_name, "")):
				yield key

	def _find_id_by_field(self, table_name: str, field_name: str, field_value: str, is_exact: bool = True, default_value = None):
		return next(self.__find_ids_by_field(table_name, field_name, field_value, is_exact), default_value)

	def __get_pool_total_rate(self, pool_code: str) -> float:
		'''
		Calculates the total drop rate for the items in the loot table
		of the pool identified by the specified ``pool_code``.

		This function accounts for stigmatas, too.
		'''
		table = self.__get_or_initialize_value(self._database, TABLE_POOLS, {})
		pool_id = self._find_id_by_field(TABLE_POOLS, "code", pool_code)
		pool = table.get(pool_id)
		if pool is None:
			return 0.0
		loot_table = pool.get("loot_table", [])
		if len(loot_table) == 0:
			return 0.0
		return GachaEditor._aggregate(loot_table, 0.0, lambda c, i: c + i.get("rate", 0.0))

	def __validate_pool_total_rate(self, pool_code: str):
		'''
		Validates the total drop rate of the pool identified by the specified ``pool_code``.
		'''
		total_rate = self.__get_pool_total_rate(pool_code)
		if not isclose(total_rate, 0.0, rel_tol=DROP_RATE_TOLERANCE) and not isclose(total_rate, 1.0, rel_tol=DROP_RATE_TOLERANCE):
			print(f"Warning! Pool '{pool_code}' has a total drop rate of {total_rate}.")

	def __find_item_id(self, item_name: str) -> str:
		'''Finds the unique identifier of the item with the specified name.'''
		return next(self.__find_ids_by_field(TABLE_ITEMS, "name", item_name), None)

	def __find_valkyrie_fragment_id(self, valkyrie_name: str) -> str:
		'''Finds the unique identifier of fragment/soul that belongs to the Valkyrie with the specified name.'''
		# TODO Mark valkyries with "is_awakened": True so it's easier to find the matching frag/soul.
		return self.__find_item_id(f"{valkyrie_name} fragment") or self.__find_item_id(f"{valkyrie_name} soul")

	def _get_next_id(self, table_name: str) -> int:
		table = self._database.get(table_name, None)
		if table is None:
			return 1
		return max((int(key) for key in table.keys()), default=0) + 1

	# TODO Make the argument parser more obvious, because specifying the "names" argument here makes no sense.
	# python .\bot\tools\database_editor.py listtables all
	def __list_tables(self, options):
		'''Lists the names of the tables available in the database.'''
		for table_id in self._database.keys():
			print(table_id)

	def __add_item_internal(self, item_name: str, item_type: str, item_rank: str = None, is_single_stigmata: bool = False) -> str:
		table = self.__get_or_initialize_value(self._database, TABLE_ITEMS, {})
		next_key = self._get_next_id(TABLE_ITEMS)
		table[next_key] = item = {
			"name": item_name,
			"type": item_type
		}
		if item_rank is not None:
			item["rank"] = item_rank
		if is_single_stigmata:
			item["is_single_stigmata"] = True
		return next_key

	# database_editor.py --type <type> [--rank <rank>] additem "name 1" "name 2"
	# database_editor.py --type 2 --rank 3 additem "name 1" "name 2"
	def __additem(self, options):
		"""Adds a new item described by the specified options to the database."""
		if not options.type:
			raise ValueError("The item type must be specified.")
		for _, item_name in enumerate(options.names):
			item_id = self.__add_item_internal(item_name, options.type, options.rank, options.single)
			print(f"Added item '{item_name}' with identifier '{item_id}'.")
		self.__save_database()

	# database_editor.py --field name finditem "name 1" "name 2"
	def __finditem(self, options):
		if not options.field:
			raise ValueError("The field name must be specified.")
		table = self.__get_or_initialize_value(self._database, TABLE_ITEMS, {})
		for name in options.names:
			for item_id in self.__find_ids_by_field(TABLE_ITEMS, options.field, name, False):
				print(f"ID: {item_id}\nData: {table[item_id]}")

	# database_editor.py deleteitem "id 1" "id 2"
	# database_editor.py --field name deleteitem "name 1" "name 2"
	def __deleteitem(self, options):
		table = self.__get_or_initialize_value(self._database, TABLE_ITEMS, {})
		has_changed = False
		for _, name in enumerate(options.names):
			if not options.field and table.pop(name, None):
				has_changed = True
				print(f"Deleted item '{name}'.")
			elif options.field is not None:
				# Since we're using a generator function, we need to iterate through a list
				# different from the original dictionary to avoid concurrent modification.
				for item_id in list(self.__find_ids_by_field(TABLE_ITEMS, options.field, name)):
					table.pop(item_id)
					has_changed = True
					print(f"Deleted item '{item_id}'.")
		if has_changed:
			self.__save_database()

	# database_editor.py [--awakened] [--rank <rank>] additemset "Valkyrie" "Weapon" "Stigmata set"
	def __additemset(self, options):
		if len(options.names) != 3:
			raise ValueError("You must specify a valid itemset: valkyrie, weapon, stigmata.")
		def add_item(name, item_type, item_rank=None):
			item_id = self.__add_item_internal(name, item_type, item_rank)
			print(f"Added item '{name}' with identifier '{item_id}'.")
		add_item(options.names[0], "0", options.rank if options.rank is not None else "2")
		if options.awakened:
			add_item(f"{options.names[0]} soul", "2")
		else:
			add_item(f"{options.names[0]} fragment", "7")
		add_item(options.names[1], "1", "3")
		add_item(options.names[2], "8", options.rank if options.rank is not None else "2")
		self.__save_database()

	# database_editor.py addpool <code> <name>
	# database_editor.py addpool ex "Expansion Battlesuit"
	def __addpool(self, options):
		if len(options.names) < 2:
			raise ValueError("The code and the name must be specified. Eg. gacha_editor.py addpool ex \"Expansion Battlesuit\"")
		table = self.__get_or_initialize_value(self._database, TABLE_POOLS, {})
		if table.get(options.names[0]) is not None:
			raise ValueError("The specified pool already exists.")
		table[self._get_next_id(TABLE_POOLS)] = {
			"name": options.names[1],
			"code": options.names[0],
			"available": True,
			"loot_table": []
		}
		self.__save_database()

	# database_editor.py removepool <code> <code> <code>
	# database_editor.py removepool ex foca focb
	def __removepool(self, options):
		table = self.__get_or_initialize_value(self._database, TABLE_POOLS, {})
		has_changed = False
		for _, name in enumerate(options.names):
			pool_id = self._find_id_by_field(TABLE_POOLS, "code", name)
			if pool_id is None:
				print(f"The pool '{name}' doesn't exist.")
				continue
			table.pop(pool_id)
			has_changed = True
			print(f"The pool '{name}' has been removed.")
		if has_changed:
			self.__save_database()

	# database_editor.py -pool <code> --rate <drop rate> addpoolitem names [names]
	# database_editor.py --pool ex --rate 0.015 addpoolitem "ARC Serratus" "Blaze Destroyer"
	def __addpoolitem(self, options):
		rate = float(options.rate)
		if rate < 0.0 or rate > 1.0:
			raise ValueError("The drop rate must be between 0.0, inclusive and 1.0, inclusive.")
		table = self.__get_or_initialize_value(self._database, TABLE_POOLS, {})
		pool_id = self._find_id_by_field(TABLE_POOLS, "code", options.pool)
		pool = table.get(pool_id)
		if pool is None:
			raise ValueError("The specified pool doesn't exist.")
		loot_table = self.__get_or_initialize_value(pool, "loot_table", [])
		matching_descriptor = None
		for descriptor in loot_table:
			# Since it's impossible to precisely compare two floating-point numbers,
			# we use a relative tolerance to check for equality.
			if not isclose(descriptor.get("rate", 0.0), rate, rel_tol=DROP_RATE_TOLERANCE):
				continue
			matching_descriptor = descriptor
			break
		has_changed = False
		if matching_descriptor is None:
			matching_descriptor = {
				"rate": rate,
				"items": []
			}
			loot_table.append(matching_descriptor)
			has_changed = True
		item_list = matching_descriptor.get("items")
		if item_list is None:
			matching_descriptor["items"] = item_list = []
		for _, name in enumerate(options.names):
			item_id = self.__find_item_id(name)
			if item_id is None:
				print(f"Item '{name}' doesn't exist, hence it won't be added to the pool.")
				continue
			if item_id in item_list:
				print(f"Item '{name}' is already added to the pool with the same rate, hence it won't be added again.")
				continue
			for descriptor_index, descriptor in enumerate(loot_table):
				other_item_list = descriptor.get("items", [])
				if item_id in other_item_list:
					other_item_list.remove(item_id)
					print(f"Item '{name}' has been removed with drop rate {descriptor.get('rate', 0.0)}.")
					if len(other_item_list) == 0:
						loot_table.pop(descriptor_index)
					break
			item_list.append(item_id)
			has_changed = True
			print(f"Added item '{name}' to the pool with drop rate {rate}.")
		print(f"There are currently {len(item_list)} items in the pool '{options.pool}' with rate {rate}.")
		self.__validate_pool_total_rate(options.pool)
		if has_changed and len(item_list) > 0:
			self.__save_database()

	# database_editor.py --pool <code> removepoolitem names [names]
	# database_editor.py --pool ex removepoolitem "ARC Serratus" "Blaze Destroyer"
	def __removepoolitem(self, options):
		table = self.__get_or_initialize_value(self._database, TABLE_POOLS, {})
		pool_id = self._find_id_by_field(TABLE_POOLS, "code", options.pool)
		pool = table.get(pool_id)
		if pool is None:
			raise ValueError("The specified pool doesn't exist.")
		loot_table = self.__get_or_initialize_value(pool, "loot_table", [])
		has_changed = False
		for _, name in enumerate(options.names):
			item_id = self.__find_item_id(name)
			if item_id is None:
				print(f"Item '{name}' doesn't exist, hence it won't be added to the pool.")
				continue
			is_found = False
			for descriptor_index, descriptor in enumerate(loot_table):
				item_list = descriptor.get("items", [])
				if item_id in item_list:
					item_list.remove(item_id)
					print(f"Item '{name}' has been removed.")
					if len(item_list) == 0:
						loot_table.pop(descriptor_index)
					is_found = True
					has_changed = True
					break
			if not is_found:
				print(f"Item '{name}' isn't in the pool, hence it won't be removed.")
		self.__validate_pool_total_rate(options.pool)
		if has_changed:
			self.__save_database()

	# database_editor.py --pool <code> [--fragments] replacepoolitem <name 1> <name 2> [<name 1> <name 2> ...]
	# database_editor.py --pool ex replacepoolitem "Stygian Nymph" "Bright Knight: Excelsis"
	def __replacepoolitem(self, options):
		if len(options.names) % 2 != 0:
			raise ValueError("You must specify name pairs.")
		pools = self.__get_or_initialize_value(self._database, TABLE_POOLS, {})
		pool_id = self._find_id_by_field(TABLE_POOLS, "code", options.pool)
		pool = pools.get(pool_id)
		if pool is None:
			raise ValueError("The specified pool doesn't exist.")
		loot_table = self.__get_or_initialize_value(pool, "loot_table", [])
		has_changed = False
		for old_item_name, new_item_name in zip(options.names[0::2], options.names[1::2]):
			if not self.__replace_pool_item(loot_table, old_item_name, new_item_name):
				continue
			has_changed = True
			if options.fragments:
				self.__replace_pool_valkyrie_fragment(loot_table, old_item_name, new_item_name)
		if has_changed:
			self.__save_database()

	def __replace_pool_item(self, loot_table, old_item_name: str, new_item_name: str) -> bool:
			old_item_id = self.__find_item_id(old_item_name)
			if old_item_id is None:
				print(f"The item '{old_item_name}' doesn't exist, hence it won't be replaced.")
				return False
			new_item_id = self.__find_item_id(new_item_name)
			if new_item_id is None:
				print(f"The item '{new_item_name}' doesn't exist, hence it won't replace the item '{old_item_name}'.")
				return False
			if self.__replace_pool_item_internal(loot_table, old_item_id, new_item_id):
				print(f"The item '{old_item_name}' has been replaced by the item '{new_item_name}'.")
				return True
			print(f"The item '{old_item_name}' cannot be found in the pool, hence it won't be replaced.")
			return False

	def __replace_pool_valkyrie_fragment(self, loot_table, old_valkyrie_name: str, new_valkyrie_name: str) -> bool:
		old_item_id = self.__find_valkyrie_fragment_id(old_valkyrie_name)
		if old_item_id is None:
			print(f"The fragment for item '{old_valkyrie_name}' doesn't exist, hence it won't be replaced.")
			return False
		new_item_id = self.__find_valkyrie_fragment_id(new_valkyrie_name)
		if new_item_id is None:
			print(f"The fragment for item '{new_valkyrie_name}' doesn't exist, hence it won't replace any other fragments.")
			return False
		if self.__replace_pool_item_internal(loot_table, old_item_id, new_item_id):
			print(f"The fragment of valkyrie '{old_valkyrie_name}' has been replaced by the fragment of valkyrie '{new_valkyrie_name}'.")
			return True
		print(f"The fragment of valkyrie '{old_valkyrie_name}' cannot be found in the pool, hence it won't be replaced.")
		return False

	def __replace_pool_item_internal(self, loot_table, old_item_id: str, new_item_id: str) -> bool:
		for _, descriptor in enumerate(loot_table):
			item_list = descriptor.get("items", [])
			if not old_item_id in item_list:
				continue
			item_list.remove(old_item_id)
			item_list.append(new_item_id)
			return True
		return False

	# database_editor.py showpool <code>
	# database_editor.py showpool ex
	def __showpool(self, options):
		pools = self.__get_or_initialize_value(self._database, TABLE_POOLS, {})
		pool_id = self._find_id_by_field(TABLE_POOLS, "code", options.names[0])
		pool = pools.get(pool_id, None)
		if pool is None:
			raise ValueError(f"The pool '{options.names[0]}' doesn't exist.")
		items = self.__get_or_initialize_value(self._database, TABLE_ITEMS, {})
		for descriptor in pool.get("loot_table", []):
			rate = descriptor.get("rate", 0.0)
			item_names = []
			for item_id in descriptor.get("items", []):
				item = items.get(item_id, {})
				item_names.append(item.get("name", "Unknown item"))
			print("Rate '{}': {}".format(rate, ", ".join(item_names)))
		print(f"Total drop rate is '{self.__get_pool_total_rate(options.names[0])}'.")

	# database_editor.py togglepool <code>
	# database_editor.py togglepool ex
	def __togglepool(self, options):
		pools = self.__get_or_initialize_value(self._database, TABLE_POOLS, {})
		pool_id = self._find_id_by_field(TABLE_POOLS, "code", options.names[0])
		pool = pools.get(pool_id, None)
		if pool is None:
			raise ValueError(f"The pool '{options.names[0]}' doesn't exist.")
		pool["available"] = new_status = not pool.get("available", False)
		self.__save_database()
		print(f"Pool '{options.names[0]}' is now {'' if new_status else 'un'}available.")

	# database_editor.py clonepool foca focb "Focused Supply B"
	def __clonepool(self, options):
		if len(options.names) != 3:
			raise ValueError("You must specify the source and the target pool identifiers, and the target pool name.")
		pools = self.__get_or_initialize_value(self._database, TABLE_POOLS, {})
		pool_id = self._find_id_by_field(TABLE_POOLS, "code", options.names[0])
		pool = pools.get(pool_id)
		if pool is None:
			raise ValueError("The pool with the specified identifier doesn't exist.")
		new_pool = deepcopy(pool)
		new_pool["name"] = options.names[2]
		new_pool["code"] = options.names[1]
		new_pool_id = self._get_next_id(TABLE_POOLS)
		self._database[TABLE_POOLS][new_pool_id] = new_pool
		self.__save_database()
		print(f"Pool '{options.names[1]}' has been created with the identifier '{new_pool_id}'.")

	def execute(self, options):
		operation = self._operations.get(options.operation)
		if operation is not None:
			print(f"Invoking operation '{options.operation}'...")
			operation(options)
			print(f"Operation '{options.operation}' finished.")
		else:
			print(f"Invalid operation '{options.operation}'.")

parser = ArgumentParser()
parser.add_argument("--type", default="0") # Item type
parser.add_argument("--rank", default=None) # Item rank
parser.add_argument("--single", action="store_const", const=True) # Is single (non-set) stigmata?
parser.add_argument("--awakened", action="store_const", const=True) # Is awakened valkyrie?
parser.add_argument("--field", default=None) # Field name
parser.add_argument("--pool", default=None) # Pool ID
parser.add_argument("--rate",  default=None) # Drop rate
parser.add_argument("--fragments", action="store_const", const=True) # Automatically handles valkyrie fragments/souls during item operations
parser.add_argument("operation") # Operation to perform
parser.add_argument("names", nargs="+")
GachaEditor().execute(parser.parse_args())
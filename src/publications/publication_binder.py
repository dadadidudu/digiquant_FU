from .bibtex import Bibtex
from ..binding.binder_options import BinderOptions
from ..binding.regex_variable_binder import RegexVariableBinder
from .publication import Publication
from ..options.individual_options import IndividualOptions
from ..options.option import Option
from ..files import Files

non_bibtex_field_options = [
	"replace",
	"entrytype",
	"citekey",
]

DEFAULT_LOGFILE_EXTENSION = ".log"

class PublicationBinder:
	"""
	Applies a RegexVariableBinder that uses the given options to the given Publication.
	This results in a Bibtex object in which key-value pairs are bound according to their regex defined in the options.
	"""

	publication: Publication
	binder_opts: BinderOptions
	binder: RegexVariableBinder
	bibtex_list: list[Bibtex]
	__logfile_path_and_name: str = None

	def __init__(self, publication: Publication, options: BinderOptions, logfile_path_and_name: str = None):
		"""
		Parameters:
			publication: the Publication object to extract data fields from
			options: the BinderOptions for the binding operation
			logfile_path_and_name: the path and name (without extension) of the logfile.
				This file will always be opened in "append" mode.
		"""

		self.publication = publication
		self.binder_opts = options
		self.binder = RegexVariableBinder(binderoptions=options)
		self.bibtex_list = []
		self.__logfile_path_and_name = logfile_path_and_name
	
	def __get_options_for_file(self) -> IndividualOptions | None:
		filename = self.publication.get_filename(with_extension=False)
		opts_for_file = self.binder_opts.get_individual_options(filename)
		return opts_for_file

	def get_bibtex(self) -> list[Bibtex]:
		"""
		Generates a list of Bibtex objects that use the constructor-given binding options
		from the constructor-given publication.
		"""

		file_options = self.__get_options_for_file()
		fields_to_add_to_all_later: list[dict[str, str]] = []

		if file_options is None:
			raise Exception("No selectors defined for " + self.publication.get_filename(with_extension=False))

		for option_entry in file_options.get_list():
			if option_entry.lower() in non_bibtex_field_options:
				continue

			html_selector = option_entry
			patterns = file_options.get_options(html_selector)
			texts_at_selector = self.publication.get_text_at(html_selector)

			for text in texts_at_selector:
				bind_text = self.__do_all_replaces(text)
				new_fields = self.__do_bind(bind_text, patterns)

				if (new_fields is None or len(new_fields) < 1):
					# no bound fields for this selector-regex entry
					message = f"No results for any of regex {patterns.get_option()} in input: {bind_text}"
					self.__write_to_log(message, "binding")
					continue

				if (patterns.is_add_key):
					fields_to_add_to_all_later.append(new_fields)
				else:
					# create  a new publication
					new_publication: Bibtex = self.__create_new_bibtex_for_fields(new_fields)
					# add new publication to existing publications
					self.bibtex_list.append(new_publication)
			
			# now we should have every defined bibtex field
			pass

		# add collected fields to add all
		for f in fields_to_add_to_all_later:
			self.__add_binding_to_all_existing_bibtex(f)

		return self.bibtex_list
				
	
	def __do_all_replaces(self, bind_text: str) -> str:
		""""
		Applies common replaces (whitespace), options-defined global replaces, and file-specific replaces on the given text.
		"""

		# do common replace (whitespace characters)
		bind_text = bind_text.replace("\n", " ")
		bind_text = bind_text.replace("\t", " ")
		bind_text = bind_text.replace("\r", " ")
		bind_text = bind_text.strip()
		
		# do global replace (options.replace)
		global_replaces = self.binder_opts.options.get("replace")
		bind_text = self.__do_replaces(global_replaces, bind_text)

		# do publication specific replace (replace)
		file_options = self.__get_options_for_file()
		specific_replace_options = file_options.get_options("replace")
		if (specific_replace_options is not None):
			bind_text = self.__do_replaces(specific_replace_options, bind_text)

		return bind_text

	def __do_replaces(self, replace_option: Option, text_to_replace_in: str) -> str:
		"""
		Applies text replace on the given string according to the given option.
		This has the format of TEXT_TO_BE_REPLACED=TEXT_TO_REPLACE_WITH
		"""

		replaces: list[str]
		if (replace_option.is_multiple):
			replaces = replace_option.get_option()
		else:
			replaces = replace_option.get_option().split(",")

		for replace_entry in replaces:
			
			if replace_entry is None or replace_entry == "":
				continue

			replace_from_to = replace_entry.split("=", 1)
			text_to_replace_in = text_to_replace_in.replace(replace_from_to[0], replace_from_to[1])

		return text_to_replace_in
	
	def __do_bind(self, bind_text: str, patterns_option: Option) -> dict[str, str]:
		"""
		Binds variables from the given text according to the given regex patterns Option object.
		"""

		bind_result: dict[str, str]
		
		if (patterns_option.is_multiple):
			patterns: list[str] = patterns_option.get_option()
			all_results: list[dict[str, str]] = []
			for pat in patterns:
				this_result = self.binder.apply(bind_text, pat)
				if (this_result is not None):
					this_result = self.__remove_invalid_entries(this_result)
					all_results.append(this_result)
			bind_result = self.__find_most_plausible_result(all_results)
		else:
			pattern: str = patterns_option.get_option()
			bind_result = self.binder.apply(bind_text, pattern)
			bind_result = self.__remove_invalid_entries(bind_result)
		return bind_result
	
	def __find_most_plausible_result(self, all_results: list[dict[str, str]]) -> dict[str, str]:
		"""
		Returns the result with the most key entries in the given list.
		If supplied in the constructor, it will output the selection process in a seperate file.
		"""
		
		most_plausible_result: dict[str, str] = {}
		for result in all_results:
			if (len(result) > len(most_plausible_result)):
				most_plausible_result = result
		if (len(most_plausible_result) > 0):
			output = f"selected {most_plausible_result} from {all_results}"
			self.__write_to_log(output, "selection")
			print(output)
		return most_plausible_result
	
	def __remove_invalid_entries(self, entries: dict[str, str]) -> dict[str, str]:
		"Removes keys that don't have any value assigned from the dictionary."

		for k in list(entries.keys()):
			if (entries[k] is None or entries[k] == str(None)):
				del entries[k]
		return entries

	def __add_binding_to_all_existing_bibtex(self, fields_to_add: dict[str, str]):
		"Adds the given key-value pairs to all the currently existing Bibtex objects."

		for b in self.bibtex_list:
			b.set_all_fields(fields_to_add)
	
	def __create_new_bibtex_for_fields(self, fields_for_new_bibtex: dict[str, str]) -> Bibtex:
		"Creates a new Bibtex object and fills it with the given key-value pairs."

		new_bibtex = Bibtex()
		new_bibtex.set_all_fields(fields_for_new_bibtex)
		return new_bibtex
	
	def __write_to_log(self, message: str, operation_name: str):
		"Writes the given message to the logfile given in the constructor. Always uses \"append\" mode."

		if (self.__logfile_path_and_name is None or self.__logfile_path_and_name == ""):
			return
		
		if ("/" in self.__logfile_path_and_name):
			idx = self.__logfile_path_and_name.rfind("/")
			directory = self.__logfile_path_and_name[:idx]
			Files.create_dir(directory)
		elif ("\\" in self.__logfile_path_and_name):
			idx = self.__logfile_path_and_name.rfind("\\")
			directory = self.__logfile_path_and_name[:idx]
			Files.create_dir(directory)

		filename = f"{self.__logfile_path_and_name}_{operation_name}{DEFAULT_LOGFILE_EXTENSION}"
		with open(filename, mode="a", encoding="utf-8") as f:
			f.write(message + "\n")
			f.write("-----\n")
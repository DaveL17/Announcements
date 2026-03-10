# TestingBase

This repo contains the shared files used in tests across the Indigo repos. The `ENV_TEMPLATE` file has the necessary
environmental values that must be set up to use this base. This repo uses the python-dotenv package to read in
environment values from a `.env` file. By default, we assume that the .env file resides in the parent directory, in 
our case `tests`, though you can specify the location in the init method.

So here's how it works - let's say we're setting up the WebServerPlugin repo. The repo should be structured like this:

```
WebServerPlugin
+- docs
+- tests
  +- shared   <- this is where you mount this submodule
  +- .env  <- this is where you set the environment vars specified in the template
  +- test_something.py  <- your test cases would subclass shared.utils.APIBase
```
### Python package requirements

In order to use this repo, you must have `python-dotenv` and `httpx` installed. The `testing-requirements.txt` file is 
always going to have the correct packages needed by this module.

## Installing and Updating the submodule

### Adding the TestingBase submodule to one of the Indigo repos

If you are checking out one of the IndigoDomotics repos, it's very likely that we've already added the submodule. You 
can tell by looking for the `.gitmodules` file at the top level of the repo. It may look something like this:

```aiignore
[submodule "tests/shared"]
	path = tests/shared
	url = https://github.com/IndigoDomotics/TestingBase.git
```

If that file is there and contains the `tests/shared` submodule definition, you'll need to init it from the command 
line:

`git submodule update --init`

That should get the initial repo. Then you can just jump down to the 
**[Updating the TestingBase submodule in your repo]()** section to update the repo as necessary.

### Adding the TestingBase submodule to your own repo

If your repo doesn't already have the submodule defined as outlined above, do this (assuming that you are at the top 
level of your repo and that your unit tests are in the `tests` directory):

`git submodule add https://github.com/IndigoDomotics/TestingBase.git tests/shared`

That will check out the repo as the tests/shared directory. This will create the `.gitmodules` file discussed above.
You can now use the features of this repo in your tests.

### Updating the TestingBase submodule in your repo

If there are changes to the this repo, you will also need to update it from the command line in your local repos (again,
if you are at the top level of your repo and you put the submodule in the tests/shared directory):

`git submodule update --recursive --remote tests/shared`

It's probably best to get in the habit of running this periodically, and especially before issuing a PR for the repo
since we'll be using the latest when we run the unit tests.

You can, of course, put the submodule anywhere you want, but for standardization purposes, we highly encourage users
of this repo to follow the structure above (and all the Indigo repos use that pattern).

**Warning**: do not update your copy of the testing module. If you need changes, please contact us and we'll discuss how
best to satisfy your needs.

## Using the TestingBase repo

The most basic usage of this submodule is to use the `APIBase` class as the super class for your test cases:

```aiignore
from shared import APIBase

class MyTestCase(APIBase):
    def __init__(self, methodName: str) -> None:
        # If you want dotenv to look for a .env file somewhere else, pass the path here. The default
        # is the current working directory so you can just not pass anything for the second arg.
        super(APIBase, self).__init__(methodName, "/my/custom/path/to/.env")
```

### APIBase

This is the primary base class for all of our tests. It is an abstract base class so you'll need to subclass it to use
it. All methods except `__init__` and `tearDown` are class methods, but you will access them in your testing functions 
as `self.send_simple_command()`, etc. The base class has a lot of functionality built-in that we don't yet document 
here, so you'll want to read through each method to see how they work. Also, if you have access to the Indigo repos you
can find lots of examples in those. We'll hopefully get these docs updated eventually (and if you want to take a swing
at it let us know, we're always looking for help).

If you override the `__init__`, `tearDown`, and/or `classSetUp` then you must call super.

### Utility functions

The `utils.py` file has some useful functions in it:

  - `run_host_script(script: str) -> str` - this will accept an Indigo Python script, run it against the IPH, and return
    whatever value the script returns. It's useful for testing functions in the IOM that don't have a corresponding API
    method (functions in the base class, `indigo.util` functions, etc.). **NOTE**: When running tests that use this 
    function, it'll take a non-trivial amount of time to spawn an IPH3 process for each call. No biggie for tests, but
    it'll slow things down. If you are calling the exact same script and expect the same result, you should cache off
    the result on the first try and use the cache for the rest of the test. You can call it at `setUpClass` time if the
    same value will be used for every test in the class (see the next function).
  - `def get_install_folder() -> pathlib.PosixPath` - this will get the path to the running install folder (uses the 
    above utility function). **Note**: we call this in the base class during class setup so that it should only be 
    called once when running all the tests in a given subclass of APIBase - caching it at startup `self._install_folder`
    for all test cases.
  - `def str_to_bool(val: str) -> bool` - returns a boolean based on the passed in string. There used to be a function 
    in `distutils` to do that, but it's going to be deprecated, so I added that definition plus a couple of additions 
    so that you can get things Indigo likes (`open`, `closed`, `locked`, etc). This function calls the `run_host_script`
    function above.
  - `def reverse_bool_str_value(val: str) -> str` - returns the opposite boolean string for the passed in string, so
    `no` for `yes`.  This function calls the `run_host_script` function above.
  - `def within_time_tolerance(dt1, dt2, tolerance_seconds=1) -> bool` - this function will take two datetime instances
    and return if they are within the specified tolerance_seconds. Useful because we pass through the event timestamp
    in all event data, so if you want to test a known payload on the action side you can use `datetime.now()` and then
    compare it to the timestamp passed through to help with that testing.

#### Troubleshooting

Here are some random things to help you troubleshoot if you run into problems.

  - If you get some nonsense about detached head in a project that uses this submodule, it perhaps means that you 
    accidentally did a `git add` on the `tests/shared` directory. You shouldn't do that since this is a submodule and git 
    will get confused if you try to actually add it. So just do a `git reset tests/shared` and that should remove it from
    the git commit list. 
  - Another thing to look for, particularly if **PyCharm is showing red** in the Git window: 
    Open the PyCharm settings and select the Version Control-> Directory Mappings to make sure that the test/shared 
    mapping is not there (it may show as unmapped, and thats OK). If `tests/shared` is listed as a separate git root, 
    **delete it**. There should only be the main project mapping in the list. PyCharm seems to want to automatically add 
    this mapping unexpectedly, so if you see a red dot in the commit window and/or a red line in the git log window,
    you should check this.

# Google Search Link Builder

Desktop tool to build Google search URLs visually.

Build searches fast, easy, save them, and open them on the program directly.

Built with Python + Tkinter.



## What it does

Google search operators are powerful but annoying to type and manage.

This tool lets you build them using a visual interface.

You add keyword groups, filters, and exclusions. The app generates the final Google search URL automatically.



## Features

### Visual Query Builder

Create Google searches without writing operators.

Supports:

* OR keyword groups
* AND keyword groups
* keyword exclusions
* site filters
* date filters



### OR Groups

Enter comma separated keywords.

Example input:

```
python automation, python scripting, workflow automation
```

Generated query:

```
("python automation" OR "python scripting" OR "workflow automation")
```

Multiple OR groups allowed.

Groups are combined using AND.



### AND Groups

Required keyword groups.

Example:

```
looking for developer, need help
```

Generated query:

```
("looking for developer" OR "need help")
```

Multiple AND groups make results more precise.



### Exclude Keywords

Filter out unwanted results.

Example:

```
-course
-tutorial
-job board
```

Useful for removing spam or irrelevant pages.



### Site Filter

Limit search to a specific website.

Examples:

```
site:reddit.com
site:stackoverflow.com
site:indeed.com
```



### Date Filters

Quick filters for recent content.

Options include:

* last 24 hours
* last 2 days
* last 3 days
* last 7 days
* last 14 days
* last 30 days

The app updates automatically when the date changes.



## Live URL Preview

The Google search URL updates instantly while you type.

You always see the final search URL before saving.



## Saved Links

Save search queries for later.

You can:

* save searches
* edit saved searches
* delete searches
* open them directly in the browser

Data is stored locally using JSON.



## Undo / Redo

Changes are tracked.

You can undo and redo recent edits.



## Backup System

Optional automatic backups when saving.

Features:

* timestamped backups
* automatic cleanup of old backups
* configurable backup limit



## Drag and Drop

If `tkinterdnd2` is installed the app supports drag and drop.

You can drag:

* text
* URLs
* files

into the interface.



## Data Files

Everything is stored locally.

```
links_data.json
settings.json
backups/
```



## Requirements

Python 3.9+

Standard libraries used:

* tkinter
* json
* os
* re
* threading
* datetime
* webbrowser
* urllib

Optional:

```
pip install tkinterdnd2
```



## Installation

Clone the repository:

```
git clone https://github.com/yourusername/google-search-link-builder.git
cd google-search-link-builder
```

Optional dependency:

```
pip install tkinterdnd2
```



## Run

```
python googlelinkcreator.py
```



## Example Use Cases

### Freelance Lead Search

Find people asking for development help.

```
("need website" OR "looking for developer")
("python" OR "automation")
site:reddit.com
```



### Market Research

Track discussions about tools or products.

```
("best automation tools" OR "workflow automation")
site:reddit.com
```



### Job Discovery

Find hidden job posts.

```
("hiring python developer" OR "need python dev")
site:linkedin.com
```



## Settings

Configurable options:

* default site filter
* default date range
* auto save
* backup on save
* maximum backups
* delete confirmation
* window size

Saved in:

```
settings.json
```


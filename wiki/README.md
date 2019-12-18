# D3A User Wiki

This repository contains the source files for the [D3A](d3a.io).

## Running locally

Note that you will need the `pip` package manager, which is generally installed with Python.

Clone the repository to your local file system.

```bash
git clone https://github.com/gridsingularity/d3a.git
```

Install `mkdocs` by using the `pip` package manager.

```bash
pip install mkdocs --user
```

Now install all necessary dependencies, once again by using `pip`.

```bash
pip install -r requirements.txt
```

Run `mkdocs serve` from the repository root to spawn a hot reloading development server and navigate to `localhost:8000` in a web browser.

## Publishing

The wiki is hosted on github and is built based on the active `master` branch on the GitHub repository. 

To publish any changes to the wiki, navigate to your local instance of the `wiki` folder in the d3a git repository, and make sure it is up to date with your requested changes. Then run:

```bash
mkdocs gh-deploy
```

This will update the site's contents by updating the `gh-pages` branch to align with the active `master` branch. Changes take approximately 1 minute to become active.

## Styling

[Mkdocs-Material](https://squidfunk.github.io/mkdocs-material/) is used to give the wiki its sleek theme.

## Contributing

Please read over the rules for contribution at the [CONTRIBUTING](CONTRIBUTING.md) document.

### Contributor set-up

As a contributor, you will need to run `npm i` in the local copy of your repository after you bring it down.

### Adding a new page

If you add a page please ensure that you give it the correct placement in the navigation by manually inputting it in the `mkdocs.yml` under the `nav` field. It is done in this way in order to have more control in how pages are displayed on the UI and give better organization to topics.

### Images

Images must be saved in the `docs/img` folder of the wiki. Image calls in the markdown files can be done as so, where `image-name.png` is the name of the file:

```bash
![img](img/image-name.png)
```

To change the size of an image, use the following size modifier:

```bash
![img](img/image-name.png){:style="height:300px;width:200px"}
```

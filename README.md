# whomineko-when-they-say

A subproject of `umineko-scripting`, for annotating/de-annotating translation scripts.

## Author

- Originally written by [ichxorya](https://github.com/ichxorya), sole member of [XanclockTranslations](https://github.com/XanclockTranslations).

- Aided by [ChatGPT](https://chatgpt.com) for code generation and improvement.

- This repository is meant to be given to [umineko-project](https://github.com/umineko-project) for further development and maintenance.

- Special thanks to [umineko-project](https://github.com/umineko-project), especially [@vit9696](https://github.com/vit9696) for answering my questions about the original script format. Also thanks to [@AbdullahTrees](https://github.com/AbdullahTrees) for initiating the discussion that led to the creation of this project.

## License

- This project is licensed under the BSD-3-Clause License. See the [LICENSE](LICENSE.md) file for details.

## Description

- This project provides 2 scripts for annotating and de-annotating translation scripts for the game "Umineko When They Cry", based on the resource at the repository [umineko-scripting](https://github.com/umineko-project/umineko-scripting).

- Why do we even have this project in the first place? Because the original translation scripts are in a format that lacks "who-said-what" annotations, making it difficult for translators and editors to work on the scripts. This project aims to solve that problem by providing tools to add (for easier editing) and remove these annotations (for compatibility with the original format).

## Usage

- Written and tested using Python 3.14. Older versions might work too, but perferably use Python >= 3.10.

- For more detailed usage instructions, please refer to the docstrings in the source code files: [annotate.py](annotate.py) and [deannotate.py](deannotate.py).

- To run the annotation script, use the following command:

  ```bash
  python annotate.py [-h] [--n N] [--out-dir OUT_DIR] [--tmp TMP] [--cleanup CLEANUP] infile
  ```

- To run the de-annotation script, use the following command:

  ```bash
  python deannotate.py [-h] [--in-dir IN_DIR] [--out-dir OUT_DIR]
  ```

## Current Limitations

- A bug has been found: I.e. ```d `+`Bốn đứa tụi tôi đang tán gẫu đủ chuyện trên trời dưới đất.`[\]``` is wrongly converted to ``` `+` ``` since the annotator misinterprets the `+` as the string to be annotated. Beware of this when using the annotator. A fix will be provided in future updates. Contributions are welcome!
- Note 2: Seems that it was the original Vietnamese script being faulty (due to my own script compiler misbehaving). Closing this for now.
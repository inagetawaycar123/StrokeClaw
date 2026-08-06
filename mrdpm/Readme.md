We have made efforts to ensure anonymity

To run this program simply:
Run the random_data.py to generate the dataset.
Run run.py (configurations such as train, test, debug, etc., can be adjusted).


To continue training or testing, modify the JSON settings("resume_state") in the config folder to specify the model to load.
Due to file size limitations, a trained model cannot be provided.
The program has been debugged and currently does not have any obvious bugs.
The initial predictor's pre-training program is not provided for now, but the code for its network structure has been given. In fact, the initial predictor only needs to be trained simply for 50 epochs using Adam with linear decay to reduce the learning rate to zero.

Usage:
Environmental requirements are listed in the requirements.txt file, but there may be omissions.
No medical images are provided directly. However, you can generate some data in the dataset using random_data, which creates test_list.txt and train_list.txt to specify the training and test sets for testing this program. Please execute the program under random_data to generate.
The training and test sets are in the dataset folder, where we have randomly generated some numpy files for you to test my program.
If you want to train on your own data, you need to specify the samples in the dataset in train_list.txt and test_list.txt and modify the data location in the config.
Normally, the pre-trained initial predictor should be placed in the project directory; it will not be loaded if it does not exist.
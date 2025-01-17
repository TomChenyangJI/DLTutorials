import json
import torch
from classifier_components import *
from get_data_from_database import *
from sklearn.model_selection import train_test_split
from transformers import BertTokenizer, BertForSequenceClassification
from transformers import LongformerTokenizer, LongformerForSequenceClassification
from sentence_transformers import SentenceTransformer
import torch.nn as nn
import torch.nn.functional as F
import warnings


# warnings.filterwarnings('ignore')

comm1 = "select * from seven limit 0, 100;"
# data = execute_command(comm1)
# for entry in data:
#     cv, overview = entry  # one sample


with open("len.json", "r") as infi:
    database_length = json.load(infi)
    # print(database_length)
    # {'seven': 100,000, 'eight': 105730, 'nine': 18285, 'ten': 928}

fetch_round = 5000
# fetch_entry_amount = {  # each round
#     "seven": 100000 // fetch_round,
#     "eight": database_length['eight'] // fetch_round,
#     "nine": database_length["nine"] // fetch_round,
#     "ten": database_length['ten'] // fetch_round
# }

fetch_entry_amount = {  # each round
    "seven": 10000 // fetch_round,
    "eight": 10000 // fetch_round,
    "nine": 10000 // fetch_round,
    "ten": database_length['ten'] // database_length['ten']
}
class10_fetch_entry_amount = fetch_entry_amount['seven'] // 10

# each time, fetch 1,000 entries from the database
# fetch data 20 times
all_val_texts = []
all_val_labels = []


# tokenizer = BertTokenizer.from_pretrained("bert-base-multilingual-cased")
# tokenizer = BertTokenizer.from_pretrained("bert-large-cased")

model_name = "allenai/longformer-base-4096"
tokenizer = LongformerTokenizer.from_pretrained(model_name)
# model = BertForSequenceClassification.from_pretrained("bert-base-uncased", num_labels=4)
model = LongformerForSequenceClassification.from_pretrained(model_name, num_labels=4, problem_type="multi_label_classification")
max_length = tokenizer.model_max_length
# print("max_length is ", max_length)
max_length = 4096
epoch_amount = 3
# sentence_model = SentenceTransformer('paraphrase-MiniLM-L6-v2')

optimizer = AdamW(model.parameters(), lr=0.001)
device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
model.to(device)

for i in range(fetch_round):
    print(f">> This is {i}-th fetching round ... ")
    comm7 = f"select * from seven limit {i * fetch_entry_amount['seven']}, {fetch_entry_amount['seven']};"
    comm8 = f"select * from seven limit {i * fetch_entry_amount['eight']}, {fetch_entry_amount['eight']};"
    comm9 = f"select * from seven limit {i * fetch_entry_amount['nine']}, {fetch_entry_amount['nine']};"
    # class10_fetch_entry_amount
    class10_exception = (i * class10_fetch_entry_amount) if (i * class10_fetch_entry_amount) <= database_length['ten'] else (i * class10_fetch_entry_amount - database_length['ten'])
    comm10 = f"select * from seven limit {class10_exception}, {class10_fetch_entry_amount};"

    data7 = execute_command(comm7)
    data8 = execute_command(comm8)
    data9 = execute_command(comm9)
    data10 = execute_command(comm10)

    # transform the data fetched from database
    data7, labels7 = transfrom_data_from_database(data7, "7")
    data8, labels8 = transfrom_data_from_database(data8, "8")
    data9, labels9 = transfrom_data_from_database(data9, "9")
    data10, labels10 = transfrom_data_from_database(data10, "10")

    data = data7 + data8 + data9 + data10

    labels = labels7 + labels8 + labels9 + labels10
    labels = torch.tensor(labels, dtype=torch.float32)

    train_texts, val_texts, train_labels, val_labels = train_test_split(data, labels, test_size=0.2)
    all_val_texts.extend(val_texts)
    all_val_labels.extend(val_labels)
    train_encodings = tokenizer(train_texts, truncation=True, padding=True, max_length=max_length)
    val_encodings = tokenizer(all_val_texts, truncation=True, padding=True, max_length=max_length)

    train_dataset = TextDataset(train_encodings, train_labels)
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)

    val_dataset = TextDataset(val_encodings, all_val_labels)
    val_loader = DataLoader(val_dataset, batch_size=32)

    for epoch in range(epoch_amount):
        print(f"\t{epoch}-th epoch")
        model.train()
        total_train_loss = 0

        for batch in train_loader:
            print("\t\tbatch...")
            batch = {k: v.to(device) for k, v in batch.items()}
            optimizer.zero_grad()
            outputs = model(**batch)
            loss = outputs.loss
            total_train_loss += loss.item()

            loss.backward()
            optimizer.step()

        avg_train_loss = total_train_loss / len(train_loader)
        print(f"\tepoch {epoch + 1}, training loss: {avg_train_loss}")

    model.eval()
    total_val_loss = 0
    correct_predictions = 0

    with torch.no_grad():
        for batch in val_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            outputs = model(**batch)
            logits = outputs.logits
            loss_fn = torch.nn.BCEWithLogitsLoss()
            loss = loss_fn(logits, batch["labels"])
            # loss = outputs.loss

            total_val_loss += loss.item()
            # predictions = torch.argmax(logits, dim=-1)
            correct_predictions += (logits == batch['labels']).sum().item()
    avg_val_loss = total_val_loss / len(val_loader)
    accuracy = correct_predictions / len(all_val_texts)
    print(f"\tvalidation loss: {avg_val_loss}")
    print(f"\tvalidation accuracy: {accuracy}")
    with open("test_result.json", "r") as infi:
        result = json.load(infi)
        result[str(i)] = {"validation loss": avg_val_loss, "validation accuracy": accuracy}
    with open("test_result.json", "w") as outfi:
        json.dump(result, outfi)

    model.save_pretrained(f"./trained_classifier_results/fetch_round_{i}")
    tokenizer.save_pretrained(f"./trained_classifier_results/fetch_round_{i}")

print("Done")

import os
import json
import fire
from tqdm import tqdm

from data_utils.data_utils import get_test_examples
from models.discriminative_aligner import DiscriminativeAligner
from models.bert_aligner import BERTAligner

from scipy.stats.stats import spearmanr, pearsonr, kendalltau


def main(dataset_name='qags_xsum',
         aspect='consistency',
         aligner_type='disc',
         disc_init=None,
         bert_model_type='roberta-large',
         dialog_context='fact_history',
         aggr_type='mean',
         remove_stopwords=False):

    if aligner_type == 'disc':
        aligner = DiscriminativeAligner.load_from_checkpoint(
            aggr_type=aggr_type, checkpoint_path=disc_init).to('cuda')
        aligner.eval()
    elif aligner_type == 'bert':
        aligner = BERTAligner(
            model_type=bert_model_type,
            aggr_type=aggr_type,
            lang='en',
            device='cuda')

    examples = get_test_examples(
        dataset_name=dataset_name, aspect=aspect, dialog_context=dialog_context)

    all_preds = []
    pred_scores, true_scores = [], []
    for example in tqdm(examples, desc='Testing'):
        if isinstance(example, list):
            if aspect == 'relevance':
                align_y_x = aligner.get_score(
                    input_text=example[0].input_text,
                    context=example[0].context,
                    remove_stopwords=remove_stopwords)
                align_r_y = aligner.get_score(
                    input_text=example[1].input_text,
                    context=example[1].context,
                    remove_stopwords=remove_stopwords)
                pred_score = align_y_x * align_r_y

            elif aspect == 'preservation':
                align_y_x = aligner.get_score(
                    input_text=example[0].input_text,
                    context=example[0].context,
                    remove_stopwords=remove_stopwords)
                align_x_y = aligner.get_score(
                    input_text=example[1].input_text,
                    context=example[1].context,
                    remove_stopwords=remove_stopwords)
                pred_score = (align_y_x * align_x_y) / (align_y_x + align_x_y)

            all_preds.append({
                'context_0': example[0].context,
                'input_text_0': example[0].input_text,
                'context_1': example[1].context,
                'input_text_1': example[1].input_text,
                'pred_score': pred_score
            })

            if pred_score is not None:
                pred_scores.append(pred_score)

                assert example[0].score == example[1].score
                true_scores.append(example[0].score)

        else:
            pred_score = aligner.get_score(
                input_text=example.input_text,
                context=example.context,
                remove_stopwords=remove_stopwords)

            all_preds.append({
                'context': example.context,
                'input_text': example.input_text,
                'pred_score': pred_score
            })

            if pred_score is not None:
                pred_scores.append(pred_score)
                true_scores.append(example.score)

    pearson_score = pearsonr(pred_scores, true_scores)[0]
    spearman_score = spearmanr(pred_scores, true_scores)[0]
    kendall_score = kendalltau(pred_scores, true_scores)[0]

    os.makedirs(f'eval_results/', exist_ok=True)
    output_filename = f'{dataset_name}_{aspect}_{aligner_type}'
    if aligner_type == 'bert':
        output_filename += f'_{bert_model_type}'

    output_path = f'eval_results/{output_filename}.json'
    json.dump(all_preds, open(output_path, 'w'), indent=4)

    print(output_filename)
    print(f'#sents: {len(pred_scores)}')
    print(f'pearson: {pearson_score:.4f}')
    print(f'spearman: {spearman_score:.4f}')
    print(f'kendall: {kendall_score:.4f}')


if __name__ == '__main__':
    fire.Fire(main)
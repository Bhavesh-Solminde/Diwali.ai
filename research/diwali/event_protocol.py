"""Bounded experiment settings, frozen before the first Diwali1.4 fit."""
from .event_data import EDGES
from .event_evaluation import FOLDS


def protocol():
    return {
        'version':'diwali1.4','stage':'August rolling development; no reserved final access',
        'folds':FOLDS,'development_folds':['A','B','C'],
        'task':'Direct26-bin distributions for15 future full-minute closes',
        'price_edges_bp':EDGES.tolist(),'zero_return':'down_or_unchanged; positive return is up',
        'primary_selection':'Three-fold/two-seed mean calibrated transfer mean15-bin log loss; simpler early-compression control breaks ties within1e-4.',
        'checkpoint_selection':'Uncalibrated selection-period mean15-bin log loss; earliest best epoch; no calibration/transfer labels for early stopping.',
        'final_build_seed':17,
        'neural_candidates':['event_temporal_conv','event_attention','one_second_temporal_conv'],
        'neural_width':64,'event_block_groups':128,'seeds':[17,29],
        'max_epochs':12,'patience':3,'batch_size':8,'optimizer':'AdamW',
        'learning_rate':0.0003,'weight_decay':0.0001,'gradient_clip':5.,
        'loss':'Equal mean cross entropy across15 price-bin heads; no future book or teacher-forced future candle inputs.',
        'normalization':'Per-fold fit-only streaming mean/std. Masked candle values excluded; no clipping or test-fitted scale.',
        'event_coverage':'Every accepted event enters learned projection; no fixed event count cap.',
        'one_second_control':'103-channel per-second means, last book state and log event counts. Explicit early compression, not identical to the earlier0.5 architecture.',
        'baselines':['fit_histogram','fit_volatility_histogram','flow_logistic','flow_boosted_trees'],
        'logistic':{'epochs':40,'patience':5,'batch_size':128,'learning_rate':0.001,'weight_decay':0.001,'seed':17},
        'boosted_trees':{'max_iter':100,'learning_rate':0.05,'max_leaf_nodes':15,'min_samples_leaf':30,'l2_regularization':1.,'early_stopping':False,'random_state':17},
        'calibration':'Separate scalar temperature for each26-bin horizon; calibration period only after checkpoint selection. If fewer than100 calibration origins, retain temperature1 for every candidate and disclose unsupported calibration.',
        'minimum_calibration_origins':100,
        'minimum_partition_origins':{'fit':200,'select':100,'calibrate':1,'score':100},
        'temperature_grid':{'min':0.5,'max':4.,'log_points':49},
        'metrics':['per_horizon_bin_log_loss','mean15_bin_log_loss','ranked_probability_score',
                   'binary_net_direction_log_loss','binary_brier','direction_accuracy','confidence_reliability','daily_paired_scores'],
        'scope':'Marginal probability fan, not a joint path distribution or entry-before-stop estimate.',
        'limitations':['Historical provider timing is assumed, not independently proven original receipt timing.',
                       'Limited valid top20 coverage and masked older candles remain explicit.',
                       'August scores are development evidence; final September evaluation stays sealed.',
                       'Finite tests cannot certify perfect conditional probabilities or profitability.'],
        'signal_lifetime':'Keep105..945-second full-candle primary outputs; separately prepared5/15/30/60-second availability-price labels are auxiliary only.',
        'lifetime_baseline':{'horizons_seconds':[5,15,30,60,105,345,945],
                             'estimator':'Independent binary logistic regressions on identical origins with fit-only normalization; C1, lbfgs, max_iter1000.',
                             'calibration':'Per-horizon scalar temperature on separate calibration dates; same0.5..4 grid.',
                             'selection':'Fixed estimator settings; do not tune from lifetime scores.',
                             'reference':'Original frozen trade reference. Auxiliary endpoint availability-price differs from full-candle execution close; report the distinction.'}}

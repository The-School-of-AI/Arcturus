import React, { useState } from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';
import { Star, Check, X, Upload, Play, GripVertical } from 'lucide-react';

// Shared Quiz Color System
const QUIZ_COLORS = {
    correct: '#10b981',    // emerald-500
    incorrect: '#ef4444',  // red-500
    pending: '#eaff00',    // neon-yellow
    neutral: '#6b7280',    // gray-500
};

interface QuizBlockProps {
    data?: any;
    config?: any;
    style?: any;
    onUpdate?: (data: any) => void;
    isInteractive?: boolean;
}

// =============================================================
// PHASE 1: SIMPLE SELECTION BLOCKS
// =============================================================

// 1. Multiple Choice Question
export const QuizMCQCard: React.FC<QuizBlockProps> = ({ data = {}, config = {}, style = {}, onUpdate, isInteractive }) => {
    const [selected, setSelected] = useState<number | null>(null);
    const [submitted, setSubmitted] = useState(false);

    const { question = 'Question?', options = ['A', 'B', 'C', 'D'], correctAnswer = 0, score = 1, explanation = '' } = data;
    const { showFeedback = true } = config;

    const handleSelect = (index: number) => {
        if (!isInteractive || submitted) return;
        setSelected(index);
    };

    const handleSubmit = () => {
        if (selected !== null) {
            setSubmitted(true);
            onUpdate?.({ userAnswer: selected, isCorrect: selected === correctAnswer });
        }
    };

    const getOptionStyle = (index: number) => {
        if (!submitted) {
            return selected === index ? 'border-neon-yellow bg-neon-yellow/10' : 'border-border hover:border-neon-yellow/50';
        }
        if (index === correctAnswer) return 'border-emerald-500 bg-emerald-500/10';
        if (index === selected && index !== correctAnswer) return 'border-red-500 bg-red-500/10';
        return 'border-border opacity-50';
    };

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full">
                <div className="flex justify-between items-start">
                    <p className="text-sm font-medium text-foreground flex-1">{question}</p>
                    <span className="text-[10px] px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full">{score} pts</span>
                </div>

                <div className="flex flex-col gap-2 flex-1">
                    {options.map((opt: string, i: number) => (
                        <button
                            key={i}
                            onClick={() => handleSelect(i)}
                            className={cn(
                                "flex items-center gap-2 p-2 rounded-lg border text-left transition-all text-xs",
                                getOptionStyle(i),
                                isInteractive && !submitted && "cursor-pointer"
                            )}
                            disabled={!isInteractive || submitted}
                        >
                            <span className="w-5 h-5 rounded-full border border-current flex items-center justify-center text-[10px] font-bold">
                                {String.fromCharCode(65 + i)}
                            </span>
                            <span className="flex-1">{opt}</span>
                            {submitted && i === correctAnswer && <Check className="w-4 h-4 text-emerald-500" />}
                            {submitted && i === selected && i !== correctAnswer && <X className="w-4 h-4 text-red-500" />}
                        </button>
                    ))}
                </div>

                {isInteractive && !submitted && selected !== null && (
                    <button onClick={handleSubmit} className="mt-2 px-4 py-2 bg-neon-yellow text-charcoal-900 rounded-lg text-xs font-bold">
                        Submit
                    </button>
                )}

                {submitted && showFeedback && explanation && (
                    <div className="mt-2 p-2 bg-muted/50 rounded text-xs text-muted-foreground">
                        {explanation}
                    </div>
                )}
            </div>
        </BaseCard>
    );
};

// 2. True/False Question
export const QuizTFCard: React.FC<QuizBlockProps> = ({ data = {}, config = {}, style = {}, onUpdate, isInteractive }) => {
    const [selected, setSelected] = useState<string | null>(null);
    const [submitted, setSubmitted] = useState(false);

    const { question = 'Is this true?', correctAnswer = 'true', score = 1, explanation = '' } = data;
    const { showFeedback = true } = config;

    const handleSelect = (value: string) => {
        if (!isInteractive || submitted) return;
        setSelected(value);
    };

    const handleSubmit = () => {
        if (selected !== null) {
            setSubmitted(true);
            onUpdate?.({ userAnswer: selected, isCorrect: selected === correctAnswer });
        }
    };

    const getButtonStyle = (value: string) => {
        if (!submitted) {
            return selected === value ? 'border-neon-yellow bg-neon-yellow/10' : 'border-border hover:border-neon-yellow/50';
        }
        if (value === correctAnswer) return 'border-emerald-500 bg-emerald-500/10';
        if (value === selected && value !== correctAnswer) return 'border-red-500 bg-red-500/10';
        return 'border-border opacity-50';
    };

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full">
                <div className="flex justify-between items-start">
                    <p className="text-sm font-medium text-foreground flex-1">{question}</p>
                    <span className="text-[10px] px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full">{score} pts</span>
                </div>

                <div className="flex gap-3 flex-1 items-center justify-center">
                    {['true', 'false'].map(val => (
                        <button
                            key={val}
                            onClick={() => handleSelect(val)}
                            className={cn(
                                "flex-1 py-4 rounded-lg border font-bold text-sm transition-all",
                                getButtonStyle(val),
                                val === 'true' ? 'text-emerald-400' : 'text-red-400'
                            )}
                            disabled={!isInteractive || submitted}
                        >
                            {val === 'true' ? 'TRUE' : 'FALSE'}
                        </button>
                    ))}
                </div>

                {isInteractive && !submitted && selected !== null && (
                    <button onClick={handleSubmit} className="px-4 py-2 bg-neon-yellow text-charcoal-900 rounded-lg text-xs font-bold">
                        Submit
                    </button>
                )}

                {submitted && showFeedback && explanation && (
                    <div className="mt-2 p-2 bg-muted/50 rounded text-xs text-muted-foreground">{explanation}</div>
                )}
            </div>
        </BaseCard>
    );
};

// 3. Multiple Answers (Checkboxes)
export const QuizMultiCard: React.FC<QuizBlockProps> = ({ data = {}, config = {}, style = {}, onUpdate, isInteractive }) => {
    const [selected, setSelected] = useState<number[]>([]);
    const [submitted, setSubmitted] = useState(false);

    const { question = 'Select all that apply:', options = ['A', 'B', 'C', 'D'], correctAnswers = [0, 1], score = 2, explanation = '' } = data;
    const { showFeedback = true, partialCredit = true } = config;

    const handleToggle = (index: number) => {
        if (!isInteractive || submitted) return;
        setSelected(prev => prev.includes(index) ? prev.filter(i => i !== index) : [...prev, index]);
    };

    const handleSubmit = () => {
        setSubmitted(true);
        const correct = correctAnswers.every((c: number) => selected.includes(c)) && selected.every(s => correctAnswers.includes(s));
        onUpdate?.({ userAnswer: selected, isCorrect: correct });
    };

    const getOptionStyle = (index: number) => {
        const isSelected = selected.includes(index);
        const isCorrect = correctAnswers.includes(index);

        if (!submitted) {
            return isSelected ? 'border-neon-yellow bg-neon-yellow/10' : 'border-border hover:border-neon-yellow/50';
        }
        if (isCorrect) return 'border-emerald-500 bg-emerald-500/10';
        if (isSelected && !isCorrect) return 'border-red-500 bg-red-500/10';
        return 'border-border opacity-50';
    };

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full">
                <div className="flex justify-between items-start">
                    <p className="text-sm font-medium text-foreground flex-1">{question}</p>
                    <span className="text-[10px] px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full">{score} pts</span>
                </div>

                <div className="flex flex-col gap-2 flex-1">
                    {options.map((opt: string, i: number) => (
                        <button
                            key={i}
                            onClick={() => handleToggle(i)}
                            className={cn("flex items-center gap-2 p-2 rounded-lg border text-left transition-all text-xs", getOptionStyle(i))}
                            disabled={!isInteractive || submitted}
                        >
                            <div className={cn(
                                "w-4 h-4 rounded border flex items-center justify-center",
                                selected.includes(i) ? 'bg-neon-yellow border-neon-yellow' : 'border-current'
                            )}>
                                {selected.includes(i) && <Check className="w-3 h-3 text-charcoal-900" />}
                            </div>
                            <span className="flex-1">{opt}</span>
                        </button>
                    ))}
                </div>

                {isInteractive && !submitted && (
                    <button onClick={handleSubmit} className="px-4 py-2 bg-neon-yellow text-charcoal-900 rounded-lg text-xs font-bold">Submit</button>
                )}

                {submitted && showFeedback && explanation && (
                    <div className="mt-2 p-2 bg-muted/50 rounded text-xs text-muted-foreground">{explanation}</div>
                )}
            </div>
        </BaseCard>
    );
};

// 4. Rating Question
export const QuizRatingCard: React.FC<QuizBlockProps> = ({ data = {}, config = {}, style = {}, onUpdate, isInteractive }) => {
    const [rating, setRating] = useState(0);
    const [hovering, setHovering] = useState(0);

    const { question = 'Rate this:', maxStars = 5, score = 0 } = data;

    const handleRate = (value: number) => {
        if (!isInteractive) return;
        setRating(value);
        onUpdate?.({ userAnswer: value });
    };

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full items-center justify-center">
                <p className="text-sm font-medium text-foreground text-center">{question}</p>

                <div className="flex gap-1">
                    {Array.from({ length: maxStars }, (_, i) => (
                        <button
                            key={i}
                            onClick={() => handleRate(i + 1)}
                            onMouseEnter={() => setHovering(i + 1)}
                            onMouseLeave={() => setHovering(0)}
                            disabled={!isInteractive}
                            className="p-1 transition-transform hover:scale-110"
                        >
                            <Star
                                className={cn(
                                    "w-8 h-8 transition-colors",
                                    (hovering || rating) >= i + 1 ? 'fill-neon-yellow text-neon-yellow' : 'text-muted-foreground'
                                )}
                            />
                        </button>
                    ))}
                </div>

                {rating > 0 && <p className="text-xs text-muted-foreground">{rating} / {maxStars}</p>}
            </div>
        </BaseCard>
    );
};

// 5. Likert Scale
export const QuizLikertCard: React.FC<QuizBlockProps> = ({ data = {}, config = {}, style = {}, onUpdate, isInteractive }) => {
    const [selected, setSelected] = useState<number | null>(null);

    const { question = 'Statement:', scaleLabels = ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'], score = 0 } = data;

    const handleSelect = (index: number) => {
        if (!isInteractive) return;
        setSelected(index);
        onUpdate?.({ userAnswer: index, label: scaleLabels[index] });
    };

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full">
                <p className="text-sm font-medium text-foreground">{question}</p>

                <div className="flex justify-between items-center gap-1">
                    {scaleLabels.map((label: string, i: number) => (
                        <button
                            key={i}
                            onClick={() => handleSelect(i)}
                            disabled={!isInteractive}
                            className={cn(
                                "flex-1 flex flex-col items-center gap-1 p-2 rounded-lg border transition-all",
                                selected === i ? 'border-neon-yellow bg-neon-yellow/10' : 'border-border hover:border-neon-yellow/30'
                            )}
                        >
                            <div className={cn(
                                "w-4 h-4 rounded-full border-2 transition-colors",
                                selected === i ? 'bg-neon-yellow border-neon-yellow' : 'border-muted-foreground'
                            )} />
                            <span className="text-[9px] text-muted-foreground text-center leading-tight">{label}</span>
                        </button>
                    ))}
                </div>
            </div>
        </BaseCard>
    );
};

// 6. Net Promoter Score (NPS)
export const QuizNPSCard: React.FC<QuizBlockProps> = ({ data = {}, config = {}, style = {}, onUpdate, isInteractive }) => {
    const [selected, setSelected] = useState<number | null>(null);

    const { question = 'How likely are you to recommend?', score = 0 } = data;

    const handleSelect = (value: number) => {
        if (!isInteractive) return;
        setSelected(value);
        onUpdate?.({ userAnswer: value });
    };

    const getScoreColor = (value: number) => {
        if (value <= 6) return 'text-red-400 border-red-400';
        if (value <= 8) return 'text-amber-400 border-amber-400';
        return 'text-emerald-400 border-emerald-400';
    };

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full">
                <p className="text-sm font-medium text-foreground text-center">{question}</p>

                <div className="flex justify-center gap-1">
                    {Array.from({ length: 11 }, (_, i) => (
                        <button
                            key={i}
                            onClick={() => handleSelect(i)}
                            disabled={!isInteractive}
                            className={cn(
                                "w-7 h-10 rounded border text-xs font-bold transition-all",
                                selected === i
                                    ? `${getScoreColor(i)} bg-current/10`
                                    : 'border-border text-muted-foreground hover:border-neon-yellow/50'
                            )}
                        >
                            {i}
                        </button>
                    ))}
                </div>

                <div className="flex justify-between text-[10px] text-muted-foreground px-1">
                    <span>Not likely</span>
                    <span>Very likely</span>
                </div>
            </div>
        </BaseCard>
    );
};

// 7. Ranking Question
export const QuizRankingCard: React.FC<QuizBlockProps> = ({ data = {}, config = {}, style = {}, onUpdate, isInteractive }) => {
    const { question = 'Rank the following:', items = ['Item 1', 'Item 2', 'Item 3', 'Item 4'], correctOrder = [0, 1, 2, 3], score = 2 } = data;
    const [ranked, setRanked] = useState<string[]>([...items]);
    const [submitted, setSubmitted] = useState(false);

    const handleSubmit = () => {
        setSubmitted(true);
        const correctItems = correctOrder.map((i: number) => items[i]);
        const isCorrect = JSON.stringify(ranked) === JSON.stringify(correctItems);
        onUpdate?.({ userAnswer: ranked, isCorrect });
    };

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full">
                <div className="flex justify-between items-start">
                    <p className="text-sm font-medium text-foreground flex-1">{question}</p>
                    <span className="text-[10px] px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full">{score} pts</span>
                </div>

                <div className="flex flex-col gap-2 flex-1">
                    {ranked.map((item, i) => (
                        <div key={i} className="flex items-center gap-2 p-2 rounded-lg border border-border bg-muted/30">
                            <GripVertical className="w-4 h-4 text-muted-foreground" />
                            <span className="w-5 h-5 rounded-full bg-neon-yellow/20 text-neon-yellow text-[10px] font-bold flex items-center justify-center">{i + 1}</span>
                            <span className="text-xs flex-1">{item}</span>
                        </div>
                    ))}
                </div>

                {isInteractive && !submitted && (
                    <button onClick={handleSubmit} className="px-4 py-2 bg-neon-yellow text-charcoal-900 rounded-lg text-xs font-bold">Submit</button>
                )}
            </div>
        </BaseCard>
    );
};

// =============================================================
// PHASE 2: INPUT-BASED BLOCKS
// =============================================================

// 8. Fill In the Blank
export const QuizFITBCard: React.FC<QuizBlockProps> = ({ data = {}, config = {}, style = {}, onUpdate, isInteractive }) => {
    const [answer, setAnswer] = useState('');
    const [submitted, setSubmitted] = useState(false);

    const { sentence = 'The answer is ___.', correctAnswer = 'blank', score = 1, explanation = '' } = data;
    const { showFeedback = true, caseSensitive = false } = config;

    const parts = sentence.split('___');

    const handleSubmit = () => {
        setSubmitted(true);
        const isCorrect = caseSensitive
            ? answer.trim() === correctAnswer
            : answer.toLowerCase().trim() === correctAnswer.toLowerCase();
        onUpdate?.({ userAnswer: answer, isCorrect });
    };

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full">
                <div className="flex justify-between items-start">
                    <div className="flex-1 text-sm text-foreground">
                        {parts[0]}
                        <input
                            type="text"
                            value={answer}
                            onChange={(e) => !submitted && setAnswer(e.target.value)}
                            disabled={!isInteractive || submitted}
                            className={cn(
                                "mx-1 px-2 py-1 border-b-2 bg-transparent text-center min-w-[80px] focus:outline-none",
                                submitted
                                    ? (answer.toLowerCase() === correctAnswer.toLowerCase() ? 'border-emerald-500 text-emerald-400' : 'border-red-500 text-red-400')
                                    : 'border-neon-yellow focus:border-neon-yellow'
                            )}
                            placeholder="..."
                        />
                        {parts[1]}
                    </div>
                    <span className="text-[10px] px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full ml-2">{score} pts</span>
                </div>

                {isInteractive && !submitted && answer && (
                    <button onClick={handleSubmit} className="px-4 py-2 bg-neon-yellow text-charcoal-900 rounded-lg text-xs font-bold self-end">Submit</button>
                )}

                {submitted && showFeedback && (
                    <div className={cn("p-2 rounded text-xs", answer.toLowerCase() === correctAnswer.toLowerCase() ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400')}>
                        {answer.toLowerCase() === correctAnswer.toLowerCase() ? 'Correct!' : `Incorrect. The answer is: ${correctAnswer}`}
                        {explanation && <p className="mt-1 text-muted-foreground">{explanation}</p>}
                    </div>
                )}
            </div>
        </BaseCard>
    );
};

// 9-23: Placeholder implementations for remaining blocks
// These follow the same pattern but with type-specific logic

export const QuizFITMBCard: React.FC<QuizBlockProps> = ({ data = {}, isInteractive }) => {
    const { passage = 'Text with ___1___ and ___2___.', score = 2 } = data;
    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-2">
                <div className="flex justify-between">
                    <p className="text-sm text-foreground">{passage}</p>
                    <span className="text-[10px] px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full">{score} pts</span>
                </div>
                <div className="text-[10px] text-muted-foreground">Fill in multiple blanks</div>
            </div>
        </BaseCard>
    );
};

export const QuizNumberCard: React.FC<QuizBlockProps> = ({ data = {}, isInteractive }) => {
    const { question = 'Enter a number:', score = 1 } = data;
    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-2">
                <div className="flex justify-between">
                    <p className="text-sm text-foreground">{question}</p>
                    <span className="text-[10px] px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full">{score} pts</span>
                </div>
                <input type="number" className="p-2 border border-border rounded bg-muted text-foreground text-sm" placeholder="Enter number..." disabled={!isInteractive} />
            </div>
        </BaseCard>
    );
};

export const QuizFormulaCard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { question = 'Formula question', formula = 'A = πr²', score = 2 } = data;
    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-2">
                <div className="flex justify-between">
                    <p className="text-sm text-foreground">{question}</p>
                    <span className="text-[10px] px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full">{score} pts</span>
                </div>
                <div className="p-2 bg-muted rounded text-center font-mono text-sm">{formula}</div>
            </div>
        </BaseCard>
    );
};

export const QuizDateCard: React.FC<QuizBlockProps> = ({ data = {}, isInteractive }) => {
    const { question = 'Select a date:', score = 1 } = data;
    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-2">
                <div className="flex justify-between">
                    <p className="text-sm text-foreground">{question}</p>
                    <span className="text-[10px] px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full">{score} pts</span>
                </div>
                <input type="date" className="p-2 border border-border rounded bg-muted text-foreground text-sm" disabled={!isInteractive} />
            </div>
        </BaseCard>
    );
};

export const QuizEssayCard: React.FC<QuizBlockProps> = ({ data = {}, config = {}, isInteractive }) => {
    const { question = 'Write your essay:', minWords = 100, maxWords = 500, score = 10 } = data;
    const { showWordCount = true } = config;
    const [text, setText] = useState('');
    const wordCount = text.trim().split(/\s+/).filter(Boolean).length;

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-2 h-full">
                <div className="flex justify-between">
                    <p className="text-sm text-foreground">{question}</p>
                    <span className="text-[10px] px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full">{score} pts</span>
                </div>
                <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    className="flex-1 p-2 border border-border rounded bg-muted text-foreground text-sm resize-none min-h-[100px]"
                    placeholder="Write your answer..."
                    disabled={!isInteractive}
                />
                {showWordCount && (
                    <div className="flex justify-between text-[10px] text-muted-foreground">
                        <span>{wordCount} words</span>
                        <span>{minWords}-{maxWords} words required</span>
                    </div>
                )}
            </div>
        </BaseCard>
    );
};

// Phase 3 & 4 blocks (simplified placeholders)
export const QuizMatchCard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { question = 'Match items:', score = 4 } = data;
    return <BaseCard><div className="p-4 text-sm"><p>{question}</p><div className="mt-2 text-[10px] text-muted-foreground">Matching UI - {score} pts</div></div></BaseCard>;
};

export const QuizDropdownCard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { score = 2 } = data;
    return <BaseCard><div className="p-4 text-sm">Multiple Dropdowns - {score} pts</div></BaseCard>;
};

export const QuizCodeCard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { question = 'Write code:', starterCode = '# Code here', language = 'python', score = 5 } = data;
    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-2 h-full">
                <div className="flex justify-between">
                    <p className="text-sm text-foreground">{question}</p>
                    <span className="text-[10px] px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full">{score} pts</span>
                </div>
                <pre className="flex-1 p-2 bg-charcoal-950 border border-border rounded text-xs font-mono text-emerald-400 overflow-auto">{starterCode}</pre>
                <div className="text-[10px] text-muted-foreground">{language}</div>
            </div>
        </BaseCard>
    );
};

export const QuizUploadCard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { question = 'Upload file:', allowedTypes = ['.pdf'], score = 10 } = data;
    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-2 items-center justify-center h-full">
                <Upload className="w-8 h-8 text-muted-foreground" />
                <p className="text-sm text-foreground text-center">{question}</p>
                <p className="text-[10px] text-muted-foreground">Allowed: {allowedTypes.join(', ')}</p>
                <span className="text-[10px] px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full">{score} pts</span>
            </div>
        </BaseCard>
    );
};

export const QuizImageCard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { question = 'Interact with image:', score = 1 } = data;
    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-2 h-full">
                <p className="text-sm text-foreground">{question}</p>
                <div className="flex-1 bg-muted rounded flex items-center justify-center text-muted-foreground text-xs">Image Area</div>
                <span className="text-[10px] px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full self-end">{score} pts</span>
            </div>
        </BaseCard>
    );
};

export const QuizTextCard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { content = 'Instructions or informational text.' } = data;
    return <BaseCard><div className="p-4 text-sm text-muted-foreground">{content}</div></BaseCard>;
};

export const QuizSectionCard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { title = 'Section', description = '' } = data;
    return (
        <BaseCard>
            <div className="p-4 border-l-4 border-neon-yellow">
                <h3 className="text-lg font-bold text-foreground">{title}</h3>
                {description && <p className="text-xs text-muted-foreground mt-1">{description}</p>}
            </div>
        </BaseCard>
    );
};

export const QuizMediaCard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { question = 'Watch and answer:', mediaType = 'video', score = 2 } = data;
    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-2 h-full">
                <p className="text-sm text-foreground">{question}</p>
                <div className="flex-1 bg-muted rounded flex items-center justify-center">
                    <Play className="w-12 h-12 text-muted-foreground" />
                </div>
                <div className="flex justify-between text-[10px] text-muted-foreground">
                    <span>{mediaType}</span>
                    <span className="px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full">{score} pts</span>
                </div>
            </div>
        </BaseCard>
    );
};

export const QuizBranchCard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { question = 'Branching question' } = data;
    return <BaseCard><div className="p-4 text-sm"><p>{question}</p><div className="mt-2 text-[10px] text-muted-foreground">Conditional Logic Block</div></div></BaseCard>;
};

export const QuizAICard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { question = 'AI-graded task:', score = 10 } = data;
    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-2 h-full">
                <div className="flex justify-between items-start">
                    <p className="text-sm text-foreground flex-1">{question}</p>
                    <span className="text-[10px] px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded-full">AI Graded</span>
                </div>
                <textarea className="flex-1 p-2 border border-border rounded bg-muted text-foreground text-sm resize-none min-h-[80px]" placeholder="Your response..." />
                <span className="text-[10px] px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full self-end">{score} pts</span>
            </div>
        </BaseCard>
    );
};

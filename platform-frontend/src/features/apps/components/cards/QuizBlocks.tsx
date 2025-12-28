import React, { useState, useCallback } from 'react';
import { BaseCard } from './BaseCard';
import { cn } from '@/lib/utils';
import { Star, Check, X, Upload, Play, GripVertical, ChevronUp, ChevronDown, ArrowRight } from 'lucide-react';

// Shared Quiz Typography & Colors - Consistent across all blocks
const QUIZ_QUESTION_CLASS = "text-sm font-medium text-foreground text-left w-full";
const QUIZ_POINTS_CLASS = "text-[10px] px-2 py-0.5 bg-neon-yellow/20 text-neon-yellow rounded-full shrink-0";

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
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <p className={QUIZ_QUESTION_CLASS}>{question}</p>
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>

                <div className="flex flex-col gap-2 flex-1 w-full">
                    {options.map((opt: string, i: number) => (
                        <button
                            key={i}
                            onClick={() => handleSelect(i)}
                            className={cn(
                                "flex items-center gap-2 p-2 rounded-lg border text-left transition-all text-xs w-full",
                                getOptionStyle(i),
                                isInteractive && !submitted && "cursor-pointer"
                            )}
                            disabled={!isInteractive || submitted}
                        >
                            <span className="w-5 h-5 rounded-full border border-current flex items-center justify-center text-[10px] font-bold shrink-0">
                                {String.fromCharCode(65 + i)}
                            </span>
                            <span className="flex-1 text-left">{opt}</span>
                            {submitted && i === correctAnswer && <Check className="w-4 h-4 text-emerald-500 shrink-0" />}
                            {submitted && i === selected && i !== correctAnswer && <X className="w-4 h-4 text-red-500 shrink-0" />}
                        </button>
                    ))}
                </div>

                {isInteractive && !submitted && selected !== null && (
                    <button onClick={handleSubmit} className="mt-2 px-4 py-2 bg-neon-yellow text-charcoal-900 rounded-lg text-xs font-bold self-start">
                        Submit
                    </button>
                )}

                {submitted && showFeedback && explanation && (
                    <div className="mt-2 p-2 bg-muted/50 rounded text-xs text-muted-foreground w-full">
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
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <p className={QUIZ_QUESTION_CLASS}>{question}</p>
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>

                <div className="flex gap-3 w-full">
                    {['true', 'false'].map(val => (
                        <button
                            key={val}
                            onClick={() => handleSelect(val)}
                            className={cn(
                                "flex-1 py-3 rounded-lg border font-bold text-sm transition-all",
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
                    <button onClick={handleSubmit} className="px-4 py-2 bg-neon-yellow text-charcoal-900 rounded-lg text-xs font-bold self-start">
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
    const { showFeedback = true } = config;

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
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <p className={QUIZ_QUESTION_CLASS}>{question}</p>
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>

                <div className="flex flex-col gap-2 flex-1 w-full">
                    {options.map((opt: string, i: number) => (
                        <button
                            key={i}
                            onClick={() => handleToggle(i)}
                            className={cn("flex items-center gap-2 p-2 rounded-lg border text-left transition-all text-xs w-full", getOptionStyle(i))}
                            disabled={!isInteractive || submitted}
                        >
                            <div className={cn(
                                "w-4 h-4 rounded border flex items-center justify-center shrink-0",
                                selected.includes(i) ? 'bg-neon-yellow border-neon-yellow' : 'border-current'
                            )}>
                                {selected.includes(i) && <Check className="w-3 h-3 text-charcoal-900" />}
                            </div>
                            <span className="flex-1 text-left">{opt}</span>
                        </button>
                    ))}
                </div>

                {isInteractive && !submitted && (
                    <button onClick={handleSubmit} className="px-4 py-2 bg-neon-yellow text-charcoal-900 rounded-lg text-xs font-bold self-start">Submit</button>
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
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <p className={QUIZ_QUESTION_CLASS}>{question}</p>

                <div className="flex gap-1 items-center">
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
                                    "w-6 h-6 transition-colors",
                                    (hovering || rating) >= i + 1 ? 'fill-neon-yellow text-neon-yellow' : 'text-muted-foreground'
                                )}
                            />
                        </button>
                    ))}
                    {rating > 0 && <span className="text-xs text-muted-foreground ml-2">{rating} / {maxStars}</span>}
                </div>
            </div>
        </BaseCard>
    );
};

// 5. Likert Scale - MATRIX FORMAT (Items on left, scale on top)
export const QuizLikertCard: React.FC<QuizBlockProps> = ({ data = {}, config = {}, style = {}, onUpdate, isInteractive }) => {
    const {
        question = 'Rate yourself in your skill',
        items = ['Python', 'PyTorch', 'AWS'],
        scaleLabels = ['No Idea', 'Bad', 'New', 'Good', 'Master'],
        score = 0
    } = data;

    const [selections, setSelections] = useState<Record<number, number>>({});

    const handleSelect = (itemIndex: number, scaleIndex: number) => {
        if (!isInteractive) return;
        setSelections(prev => ({ ...prev, [itemIndex]: scaleIndex }));
        onUpdate?.({ userAnswer: { ...selections, [itemIndex]: scaleIndex } });
    };

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-4 h-full w-full">
                <p className={QUIZ_QUESTION_CLASS}>{question}</p>

                {/* Scale Header */}
                <div className="w-full overflow-x-auto">
                    <table className="w-full border-collapse">
                        <thead>
                            <tr>
                                <th className="text-left p-2 text-xs text-muted-foreground font-normal w-[120px]"></th>
                                {scaleLabels.map((label: string, i: number) => (
                                    <th key={i} className="p-2 text-[11px] text-muted-foreground font-normal text-center min-w-[80px]">
                                        {label}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {items.map((item: string, itemIdx: number) => (
                                <tr key={itemIdx} className="border-t border-border/30">
                                    <td className="p-2 text-sm text-foreground">{item}</td>
                                    {scaleLabels.map((_: string, scaleIdx: number) => (
                                        <td key={scaleIdx} className="p-2 text-center">
                                            <button
                                                onClick={() => handleSelect(itemIdx, scaleIdx)}
                                                disabled={!isInteractive}
                                                className={cn(
                                                    "w-5 h-5 rounded-full border-2 transition-all",
                                                    selections[itemIdx] === scaleIdx
                                                        ? 'bg-neon-yellow border-neon-yellow'
                                                        : 'border-muted-foreground/50 hover:border-neon-yellow/50'
                                                )}
                                            />
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </BaseCard>
    );
};

// 6. Net Promoter Score (NPS) - RECTANGULAR BOXES, FULL WIDTH
export const QuizNPSCard: React.FC<QuizBlockProps> = ({ data = {}, config = {}, style = {}, onUpdate, isInteractive }) => {
    const [selected, setSelected] = useState<number | null>(null);

    const { question = 'How likely are you to recommend us to a friend or colleague?', score = 0 } = data;

    const handleSelect = (value: number) => {
        if (!isInteractive) return;
        setSelected(value);
        onUpdate?.({ userAnswer: value });
    };

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <p className={QUIZ_QUESTION_CLASS}>{question}</p>

                {/* NPS Scale - Full Width Rectangular Boxes */}
                <div className="flex w-full">
                    {Array.from({ length: 11 }, (_, i) => (
                        <button
                            key={i}
                            onClick={() => handleSelect(i)}
                            disabled={!isInteractive}
                            className={cn(
                                "flex-1 py-2 border text-xs font-medium transition-all",
                                i === 0 ? 'rounded-l-lg' : '',
                                i === 10 ? 'rounded-r-lg' : '',
                                i > 0 ? 'border-l-0' : '',
                                selected === i
                                    ? 'bg-neon-yellow text-charcoal-900 border-neon-yellow'
                                    : 'border-border text-foreground hover:bg-muted/50'
                            )}
                        >
                            {i}
                        </button>
                    ))}
                </div>

                {/* Labels */}
                <div className="flex justify-between text-[11px] text-muted-foreground">
                    <span>Not at all likely</span>
                    <span>Extremely likely</span>
                </div>
            </div>
        </BaseCard>
    );
};

// 7. Ranking Question - WITH DRAG & DROP
export const QuizRankingCard: React.FC<QuizBlockProps> = ({ data = {}, config = {}, style = {}, onUpdate, isInteractive }) => {
    const { question = 'Rank the following:', items = ['Item 1', 'Item 2', 'Item 3', 'Item 4'], correctOrder = [0, 1, 2, 3], score = 2 } = data;
    const [ranked, setRanked] = useState<string[]>([...items]);
    const [submitted, setSubmitted] = useState(false);
    const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
    const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

    const handleDragStart = (e: React.DragEvent, index: number) => {
        if (!isInteractive || submitted) {
            e.preventDefault();
            return;
        }
        e.stopPropagation();
        setDraggedIndex(index);
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', index.toString());
    };

    const handleDragOver = (e: React.DragEvent, index: number) => {
        e.preventDefault();
        e.stopPropagation();
        if (!isInteractive || submitted || draggedIndex === null) return;
        setDragOverIndex(index);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.stopPropagation();
        setDragOverIndex(null);
    };

    const handleDrop = (e: React.DragEvent, toIndex: number) => {
        e.preventDefault();
        e.stopPropagation();
        if (!isInteractive || submitted || draggedIndex === null) return;

        if (draggedIndex !== toIndex) {
            const newRanked = [...ranked];
            const [removed] = newRanked.splice(draggedIndex, 1);
            newRanked.splice(toIndex, 0, removed);
            setRanked(newRanked);
        }
        setDraggedIndex(null);
        setDragOverIndex(null);
    };

    const handleDragEnd = (e: React.DragEvent) => {
        e.stopPropagation();
        setDraggedIndex(null);
        setDragOverIndex(null);
    };

    const moveItem = (fromIndex: number, direction: 'up' | 'down') => {
        if (!isInteractive || submitted) return;
        const toIndex = direction === 'up' ? fromIndex - 1 : fromIndex + 1;
        if (toIndex < 0 || toIndex >= ranked.length) return;

        const newRanked = [...ranked];
        [newRanked[fromIndex], newRanked[toIndex]] = [newRanked[toIndex], newRanked[fromIndex]];
        setRanked(newRanked);
    };

    const handleSubmit = () => {
        setSubmitted(true);
        const correctItems = correctOrder.map((i: number) => items[i]);
        const isCorrect = JSON.stringify(ranked) === JSON.stringify(correctItems);
        onUpdate?.({ userAnswer: ranked, isCorrect });
    };

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <p className={QUIZ_QUESTION_CLASS}>{question}</p>
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>

                <div className="flex flex-col gap-2 flex-1 w-full">
                    {ranked.map((item, i) => (
                        <div
                            key={`${item}-${i}`}
                            draggable={isInteractive && !submitted}
                            onDragStart={(e) => handleDragStart(e, i)}
                            onDragOver={(e) => handleDragOver(e, i)}
                            onDragLeave={(e) => handleDragLeave(e)}
                            onDrop={(e) => handleDrop(e, i)}
                            onDragEnd={(e) => handleDragEnd(e)}
                            className={cn(
                                "flex items-center gap-2 p-2 rounded-lg border bg-muted/30 w-full transition-all",
                                draggedIndex === i && "opacity-50 border-neon-yellow",
                                dragOverIndex === i && draggedIndex !== i && "border-neon-yellow bg-neon-yellow/10",
                                isInteractive && !submitted ? "cursor-grab active:cursor-grabbing border-border" : "border-border"
                            )}
                        >
                            {/* Move Buttons */}
                            <div className="flex flex-col gap-0.5">
                                <button
                                    onClick={() => moveItem(i, 'up')}
                                    disabled={!isInteractive || submitted || i === 0}
                                    className={cn("p-0.5 rounded hover:bg-muted transition-colors", i === 0 && "opacity-30")}
                                >
                                    <ChevronUp className="w-3 h-3 text-muted-foreground" />
                                </button>
                                <button
                                    onClick={() => moveItem(i, 'down')}
                                    disabled={!isInteractive || submitted || i === ranked.length - 1}
                                    className={cn("p-0.5 rounded hover:bg-muted transition-colors", i === ranked.length - 1 && "opacity-30")}
                                >
                                    <ChevronDown className="w-3 h-3 text-muted-foreground" />
                                </button>
                            </div>
                            <GripVertical className="w-4 h-4 text-muted-foreground shrink-0 cursor-grab" />
                            <span className="w-5 h-5 rounded-full bg-neon-yellow/20 text-neon-yellow text-[10px] font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                            <span className="text-xs flex-1 text-left">{item}</span>
                        </div>
                    ))}
                </div>

                {isInteractive && !submitted && (
                    <button onClick={handleSubmit} className="px-4 py-2 bg-neon-yellow text-charcoal-900 rounded-lg text-xs font-bold self-start">Submit</button>
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
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <div className="flex-1 text-sm text-foreground text-left">
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
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>

                {isInteractive && !submitted && answer && (
                    <button onClick={handleSubmit} className="px-4 py-2 bg-neon-yellow text-charcoal-900 rounded-lg text-xs font-bold self-start">Submit</button>
                )}

                {submitted && showFeedback && (
                    <div className={cn("p-2 rounded text-xs w-full", answer.toLowerCase() === correctAnswer.toLowerCase() ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400')}>
                        {answer.toLowerCase() === correctAnswer.toLowerCase() ? 'Correct!' : `Incorrect. The answer is: ${correctAnswer}`}
                        {explanation && <p className="mt-1 text-muted-foreground">{explanation}</p>}
                    </div>
                )}
            </div>
        </BaseCard>
    );
};

// 9. Fill In Multiple Blanks
export const QuizFITMBCard: React.FC<QuizBlockProps> = ({ data = {}, config = {}, isInteractive }) => {
    const { passage = 'The ___1___ is the largest organ. The ___2___ pumps blood.', correctAnswers = ['skin', 'heart'], score = 2 } = data;
    const [answers, setAnswers] = useState<string[]>(new Array(correctAnswers.length).fill(''));

    const handleChange = (index: number, value: string) => {
        const newAnswers = [...answers];
        newAnswers[index] = value;
        setAnswers(newAnswers);
    };

    // Split passage by blank placeholders
    const parts = passage.split(/___\d___/);

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <div className="flex-1 text-sm text-foreground text-left leading-relaxed">
                        {parts.map((part: string, i: number) => (
                            <React.Fragment key={i}>
                                {part}
                                {i < parts.length - 1 && (
                                    <input
                                        type="text"
                                        value={answers[i] || ''}
                                        onChange={(e) => handleChange(i, e.target.value)}
                                        disabled={!isInteractive}
                                        className="mx-1 px-2 py-0.5 border-b-2 border-neon-yellow bg-transparent text-center w-20 focus:outline-none text-sm"
                                        placeholder={`(${i + 1})`}
                                    />
                                )}
                            </React.Fragment>
                        ))}
                    </div>
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>
            </div>
        </BaseCard>
    );
};

// 10. Numerical Answer
export const QuizNumberCard: React.FC<QuizBlockProps> = ({ data = {}, isInteractive }) => {
    const { question = 'What is 15 × 8?', correctAnswer = 120, tolerance = 0, score = 1 } = data;
    const [answer, setAnswer] = useState('');

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <p className={QUIZ_QUESTION_CLASS}>{question}</p>
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>
                <input
                    type="number"
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                    className="p-2 border border-border rounded bg-muted text-foreground text-sm w-full"
                    placeholder="Enter number..."
                    disabled={!isInteractive}
                />
            </div>
        </BaseCard>
    );
};

// 11. Formula Question
export const QuizFormulaCard: React.FC<QuizBlockProps> = ({ data = {}, isInteractive }) => {
    const { question = 'Calculate the area of a circle with radius r.', formula = 'A = πr²', score = 2 } = data;
    const [answer, setAnswer] = useState('');

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <p className={QUIZ_QUESTION_CLASS}>{question}</p>
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>
                <div className="p-3 bg-muted/50 rounded font-mono text-sm text-center border border-border">{formula}</div>
                <input
                    type="number"
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                    className="p-2 border border-border rounded bg-muted text-foreground text-sm w-full"
                    placeholder="Your answer..."
                    disabled={!isInteractive}
                />
            </div>
        </BaseCard>
    );
};

// 12. Date Question
export const QuizDateCard: React.FC<QuizBlockProps> = ({ data = {}, isInteractive }) => {
    const { question = 'When did World War II end?', score = 1 } = data;

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <p className={QUIZ_QUESTION_CLASS}>{question}</p>
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>
                <input type="date" className="p-2 border border-border rounded bg-muted text-foreground text-sm w-full" disabled={!isInteractive} />
            </div>
        </BaseCard>
    );
};

// 13. Essay Question
export const QuizEssayCard: React.FC<QuizBlockProps> = ({ data = {}, config = {}, isInteractive }) => {
    const { question = 'Discuss the causes and effects of climate change.', minWords = 100, maxWords = 500, score = 10 } = data;
    const { showWordCount = true } = config;
    const [text, setText] = useState('');
    const wordCount = text.trim().split(/\s+/).filter(Boolean).length;

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <p className={QUIZ_QUESTION_CLASS}>{question}</p>
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>
                <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    className="flex-1 p-2 border border-border rounded bg-muted text-foreground text-sm resize-none min-h-[100px] w-full"
                    placeholder="Write your answer..."
                    disabled={!isInteractive}
                />
                {showWordCount && (
                    <div className="flex justify-between text-[10px] text-muted-foreground w-full">
                        <span>{wordCount} words</span>
                        <span>{minWords}-{maxWords} words required</span>
                    </div>
                )}
            </div>
        </BaseCard>
    );
};

// =============================================================
// PHASE 3: ADVANCED INTERACTIVE BLOCKS
// =============================================================

// 14. Matching Question - FULL FUNCTIONAL UI
export const QuizMatchCard: React.FC<QuizBlockProps> = ({ data = {}, config = {}, isInteractive }) => {
    const {
        question = 'Match each country with its capital:',
        leftItems = ['France', 'Japan', 'Brazil', 'Egypt'],
        rightItems = ['Tokyo', 'Paris', 'Cairo', 'Brasília'],
        score = 4
    } = data;

    const [matches, setMatches] = useState<Record<number, number | null>>({});
    const [selectedLeft, setSelectedLeft] = useState<number | null>(null);

    const handleLeftClick = (index: number) => {
        if (!isInteractive) return;
        setSelectedLeft(index);
    };

    const handleRightClick = (index: number) => {
        if (!isInteractive || selectedLeft === null) return;
        setMatches(prev => ({ ...prev, [selectedLeft]: index }));
        setSelectedLeft(null);
    };

    const getMatchedRight = (leftIndex: number): number | null => {
        return matches[leftIndex] ?? null;
    };

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-4 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <p className={QUIZ_QUESTION_CLASS}>{question}</p>
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>

                <div className="flex gap-4 w-full">
                    {/* Left Column */}
                    <div className="flex-1 flex flex-col gap-2">
                        {leftItems.map((item: string, i: number) => (
                            <button
                                key={i}
                                onClick={() => handleLeftClick(i)}
                                className={cn(
                                    "p-2 rounded-lg border text-xs text-left transition-all",
                                    selectedLeft === i ? 'border-neon-yellow bg-neon-yellow/10' : 'border-border hover:border-neon-yellow/50',
                                    getMatchedRight(i) !== null && 'border-emerald-500/50 bg-emerald-500/5'
                                )}
                            >
                                <span className="font-medium">{item}</span>
                                {getMatchedRight(i) !== null && (
                                    <span className="ml-2 text-emerald-400">→ {rightItems[getMatchedRight(i)!]}</span>
                                )}
                            </button>
                        ))}
                    </div>

                    {/* Arrow */}
                    <div className="flex items-center">
                        <ArrowRight className="w-5 h-5 text-muted-foreground" />
                    </div>

                    {/* Right Column */}
                    <div className="flex-1 flex flex-col gap-2">
                        {rightItems.map((item: string, i: number) => {
                            const isMatched = Object.values(matches).includes(i);
                            return (
                                <button
                                    key={i}
                                    onClick={() => handleRightClick(i)}
                                    disabled={isMatched}
                                    className={cn(
                                        "p-2 rounded-lg border text-xs text-left transition-all",
                                        isMatched ? 'border-emerald-500/50 bg-emerald-500/5 opacity-50' : 'border-border hover:border-neon-yellow/50',
                                        selectedLeft !== null && !isMatched && 'hover:bg-neon-yellow/10'
                                    )}
                                >
                                    {item}
                                </button>
                            );
                        })}
                    </div>
                </div>
            </div>
        </BaseCard>
    );
};

// 15. Multiple Dropdowns - FULL FUNCTIONAL UI
export const QuizDropdownCard: React.FC<QuizBlockProps> = ({ data = {}, isInteractive }) => {
    const {
        content = {
            text: 'The {0} is the powerhouse of the cell. DNA is stored in the {1}.',
            dropdowns: [
                { options: ['Nucleus', 'Mitochondria', 'Ribosome'], correct: 1 },
                { options: ['Cytoplasm', 'Nucleus', 'Cell Wall'], correct: 1 }
            ]
        },
        score = 2
    } = data;

    const [selections, setSelections] = useState<Record<number, string>>({});

    const handleChange = (index: number, value: string) => {
        setSelections(prev => ({ ...prev, [index]: value }));
    };

    // Parse text and insert dropdowns
    const renderContent = () => {
        const text = content.text || '';
        const parts = text.split(/\{(\d)\}/);

        return parts.map((part: string, i: number) => {
            // Check if this is a dropdown index
            const dropdownIndex = parseInt(part);
            if (!isNaN(dropdownIndex) && content.dropdowns && content.dropdowns[dropdownIndex]) {
                const dropdown = content.dropdowns[dropdownIndex];
                return (
                    <select
                        key={i}
                        value={selections[dropdownIndex] || ''}
                        onChange={(e) => handleChange(dropdownIndex, e.target.value)}
                        disabled={!isInteractive}
                        className="mx-1 px-2 py-1 border border-neon-yellow/50 rounded bg-muted text-foreground text-sm focus:outline-none focus:border-neon-yellow"
                    >
                        <option value="">Select...</option>
                        {dropdown.options.map((opt: string, j: number) => (
                            <option key={j} value={opt}>{opt}</option>
                        ))}
                    </select>
                );
            }
            return <span key={i}>{part}</span>;
        });
    };

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <p className="text-sm text-foreground text-left leading-relaxed flex-1 flex flex-wrap items-center">
                        {renderContent()}
                    </p>
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>
            </div>
        </BaseCard>
    );
};

// 16. Code Editor
export const QuizCodeCard: React.FC<QuizBlockProps> = ({ data = {}, isInteractive }) => {
    const { question = 'Write a function that returns the sum of two numbers.', starterCode = 'def add(a, b):\n    # Your code here\n    pass', language = 'python', score = 5 } = data;
    const [code, setCode] = useState(starterCode);

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <p className={QUIZ_QUESTION_CLASS}>{question}</p>
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>
                <textarea
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    className="flex-1 p-3 bg-charcoal-950 border border-border rounded text-xs font-mono text-emerald-400 resize-none min-h-[120px] w-full"
                    disabled={!isInteractive}
                    spellCheck={false}
                />
                <div className="text-[10px] text-muted-foreground">{language}</div>
            </div>
        </BaseCard>
    );
};

// 17. File Upload
export const QuizUploadCard: React.FC<QuizBlockProps> = ({ data = {}, isInteractive }) => {
    const { question = 'Upload your completed assignment (PDF or DOCX).', allowedTypes = ['.pdf', '.docx'], maxSize = 10, score = 10 } = data;

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <p className={QUIZ_QUESTION_CLASS}>{question}</p>
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>
                <div className="flex-1 border-2 border-dashed border-border rounded-lg flex flex-col items-center justify-center gap-2 p-4 hover:border-neon-yellow/50 transition-colors cursor-pointer">
                    <Upload className="w-8 h-8 text-muted-foreground" />
                    <p className="text-xs text-muted-foreground">Click to upload or drag and drop</p>
                    <p className="text-[10px] text-muted-foreground">Allowed: {allowedTypes.join(', ')} (Max {maxSize}MB)</p>
                </div>
            </div>
        </BaseCard>
    );
};

// 18. Image Interaction
export const QuizImageCard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { question = 'Click on the brain in this image.', score = 1 } = data;
    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <p className={QUIZ_QUESTION_CLASS}>{question}</p>
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>
                <div className="flex-1 bg-muted rounded flex items-center justify-center text-muted-foreground text-xs min-h-[100px]">
                    Image Area (Click to add image)
                </div>
            </div>
        </BaseCard>
    );
};

// =============================================================
// PHASE 4: STRUCTURAL & AI BLOCKS
// =============================================================

// 19. Text (No Question)
export const QuizTextCard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { content = '## Instructions\n\nRead the following passage carefully before answering the questions below.' } = data;
    return (
        <BaseCard>
            <div className="p-4 text-sm text-muted-foreground text-left w-full">
                {content}
            </div>
        </BaseCard>
    );
};

// 20. Section Header
export const QuizSectionCard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { title = 'Section 1: Multiple Choice', description = 'Answer all questions in this section. Each question is worth 1 point.' } = data;
    return (
        <BaseCard>
            <div className="p-4 border-l-4 border-neon-yellow w-full">
                <h3 className="text-lg font-bold text-foreground text-left">{title}</h3>
                {description && <p className="text-xs text-muted-foreground mt-1 text-left">{description}</p>}
            </div>
        </BaseCard>
    );
};

// 21. Media-Based Question
export const QuizMediaCard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { question = 'Watch the video and answer the question below.', mediaType = 'video', score = 2 } = data;
    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <p className={QUIZ_QUESTION_CLASS}>{question}</p>
                    <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                </div>
                <div className="flex-1 bg-muted rounded flex items-center justify-center min-h-[100px]">
                    <Play className="w-12 h-12 text-muted-foreground" />
                </div>
                <div className="text-[10px] text-muted-foreground">{mediaType.toUpperCase()}</div>
            </div>
        </BaseCard>
    );
};

// 22. Conditional / Branching Question
export const QuizBranchCard: React.FC<QuizBlockProps> = ({ data = {} }) => {
    const { question = 'Did you complete the prerequisite course?' } = data;
    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <p className={QUIZ_QUESTION_CLASS}>{question}</p>
                <div className="flex gap-2">
                    <button className="flex-1 py-2 rounded-lg border border-border text-xs hover:border-neon-yellow/50 transition-all">Yes</button>
                    <button className="flex-1 py-2 rounded-lg border border-border text-xs hover:border-neon-yellow/50 transition-all">No</button>
                </div>
                <div className="text-[10px] text-muted-foreground bg-muted/50 p-2 rounded">
                    ⚡ Conditional Logic Block
                </div>
            </div>
        </BaseCard>
    );
};

// 23. AI-Graded Task
export const QuizAICard: React.FC<QuizBlockProps> = ({ data = {}, isInteractive }) => {
    const { question = 'Explain the concept of machine learning in your own words.', score = 10 } = data;
    const [text, setText] = useState('');

    return (
        <BaseCard>
            <div className="p-4 flex flex-col gap-3 h-full w-full">
                <div className="flex justify-between items-start gap-2 w-full">
                    <p className={QUIZ_QUESTION_CLASS}>{question}</p>
                    <div className="flex gap-1 shrink-0">
                        <span className="text-[10px] px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded-full">AI Graded</span>
                        <span className={QUIZ_POINTS_CLASS}>{score} pts</span>
                    </div>
                </div>
                <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    className="flex-1 p-2 border border-border rounded bg-muted text-foreground text-sm resize-none min-h-[80px] w-full"
                    placeholder="Your response..."
                    disabled={!isInteractive}
                />
            </div>
        </BaseCard>
    );
};

import { useState } from "react";
import {
  generateQuiz,
  generateStudyPlan,
  submitQuiz,
} from "../services/api.js";

const OPTION_IDS = ["A", "B", "C", "D"];

export default function QuizGeneratorPage() {
  const [topic, setTopic] = useState("");
  const [notes, setNotes] = useState("");
  const [numQuestions, setNumQuestions] = useState("5");
  const [difficulty, setDifficulty] = useState("easy");
  const [quiz, setQuiz] = useState(null);
  const [answers, setAnswers] = useState({});
  const [results, setResults] = useState(null);
  const [studyPlan, setStudyPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [planLoading, setPlanLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleGenerate(event) {
    event.preventDefault();
    if (!topic.trim() && !notes.trim()) {
      setError("Enter a topic or paste your study notes to get started.");
      return;
    }

    setLoading(true);
    setError("");
    setQuiz(null);
    setResults(null);
    setStudyPlan(null);
    setAnswers({});
    try {
      const generated = await generateQuiz({
        topic: topic.trim() || null,
        notes: notes.trim() || null,
        num_questions: Number(numQuestions),
        difficulty,
      });
      setQuiz(generated);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmitQuiz() {
    if (!quiz || results || loading) return;
    setLoading(true);
    setError("");
    try {
      const submitted = await submitQuiz(
        quiz.quiz_id,
        quiz.questions.map((question) => ({
          question_id: question.question_id,
          selected_answer: answers[question.question_id] || null,
        })),
      );
      setResults(submitted);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateStudyPlan() {
    if (!quiz || !results || results.incorrect_answers === 0 || planLoading) return;

    setPlanLoading(true);
    setError("");
    try {
      const plan = await generateStudyPlan(quiz.quiz_id);
      setStudyPlan(plan);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setPlanLoading(false);
    }
  }

  function resetQuiz() {
    setQuiz(null);
    setAnswers({});
    setResults(null);
    setStudyPlan(null);
    setError("");
  }

  return (
    <div className="quiz-page">
      {!quiz ? (
        <form className="academic-panel quiz-setup" onSubmit={handleGenerate}>
          <div className="quiz-panel-heading">
            <div>
              <h2>Create a practice quiz</h2>
              <p>Choose a topic or paste notes, then let your AI tutor prepare questions.</p>
            </div>
          </div>

          <div className="quiz-field-grid">
            <label className="quiz-field">
              <span>Topic <small>(optional if you provide notes)</small></span>
              <input
                type="text"
                maxLength={200}
                value={topic}
                onChange={(event) => setTopic(event.target.value)}
                placeholder="e.g. Python functions"
              />
            </label>
            <label className="quiz-field">
              <span>Study notes <small>(optional if you provide a topic)</small></span>
              <textarea
                maxLength={10000}
                rows={5}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Paste notes here. The quiz will focus on the material you provide."
              />
            </label>
            <div className="quiz-choice-grid">
              <label className="quiz-field">
                <span>Number of questions</span>
                <select
                  value={numQuestions}
                  onChange={(event) => setNumQuestions(event.target.value)}
                >
                  <option value="5">5 questions</option>
                  <option value="10">10 questions</option>
                  <option value="15">15 questions</option>
                </select>
              </label>
              <label className="quiz-field">
                <span>Difficulty</span>
                <select
                  value={difficulty}
                  onChange={(event) => setDifficulty(event.target.value)}
                >
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </label>
            </div>
          </div>

          {error && <p className="quiz-error" role="alert">{error}</p>}
          <div className="quiz-form-actions">
            <span>Generated questions are checked before they’re shown.</span>
            <button className="primary-button quiz-primary-button" type="submit" disabled={loading}>
              {loading ? "Generating quiz…" : "Generate quiz"}
            </button>
          </div>
          {loading && (
            <p className="quiz-loading" role="status">
              <span className="loading-spinner" />
              Your AI tutor is preparing the questions. This can take a little while.
            </p>
          )}
        </form>
      ) : (
        <>
          {!results ? (
            <section className="academic-panel quiz-taking">
              <div className="quiz-panel-heading quiz-taking-heading">
                <div>
                  <h2>{quiz.topic || "Quiz from your study notes"}</h2>
                  <p>
                    {quiz.num_questions} questions · {quiz.difficulty} difficulty
                  </p>
                </div>
                <span className="quiz-progress">
                  {Object.keys(answers).length} / {quiz.num_questions} answered
                </span>
              </div>

              <div className="quiz-question-list">
                {quiz.questions.map((question, index) => (
                  <fieldset className="quiz-question" key={question.question_id}>
                    <legend>
                      <span>Question {index + 1}</span>
                      {question.question}
                    </legend>
                    <div className="quiz-options">
                      {OPTION_IDS.map((optionId) => (
                        <label
                          className={`quiz-option${answers[question.question_id] === optionId ? " selected" : ""}`}
                          key={optionId}
                        >
                          <input
                            type="radio"
                            name={question.question_id}
                            value={optionId}
                            checked={answers[question.question_id] === optionId}
                            onChange={() =>
                              setAnswers((current) => ({
                                ...current,
                                [question.question_id]: optionId,
                              }))
                            }
                          />
                          <span className="quiz-option-id">{optionId}</span>
                          <span>{question.options[optionId]}</span>
                        </label>
                      ))}
                    </div>
                  </fieldset>
                ))}
              </div>

              {error && <p className="quiz-error" role="alert">{error}</p>}
              <div className="quiz-submit-row">
                <span>Unanswered questions count as incorrect.</span>
                <button
                  className="primary-button quiz-primary-button"
                  type="button"
                  onClick={handleSubmitQuiz}
                  disabled={loading}
                >
                  {loading ? "Checking answers…" : "Submit quiz"}
                </button>
              </div>
            </section>
          ) : (
            <section className="academic-panel quiz-results">
              <header className="quiz-result-summary">
                <p className="eyebrow">QUIZ COMPLETE</p>
                <h2>
                  {results.correct_answers} / {results.total_questions} correct
                </h2>
                <strong>{results.score_percentage}%</strong>
                <p>
                  {results.correct_answers} correct · {results.incorrect_answers} incorrect
                </p>
              </header>

              <div className="quiz-question-list">
                {results.results.map((result, index) => (
                  <article
                    className={`quiz-result-question${result.is_correct ? " correct" : " incorrect"}`}
                    key={result.question_id}
                  >
                    <h3>Question {index + 1}: {result.question}</h3>
                    <p>
                      Your answer:{" "}
                      <strong>
                        {result.selected_answer
                          ? `${result.selected_answer}. ${result.options[result.selected_answer]}`
                          : "Not answered"}
                      </strong>
                    </p>
                    <p>
                      Correct answer:{" "}
                      <strong>
                        {result.correct_answer}. {result.options[result.correct_answer]}
                      </strong>
                    </p>
                    <p className="quiz-explanation">{result.explanation}</p>
                  </article>
                ))}
              </div>
              {results.incorrect_answers > 0 && (
                <section className="study-plan-panel" aria-labelledby="study-plan-heading">
                  <div className="study-plan-heading">
                    <div>
                      <h3 id="study-plan-heading">Turn mistakes into a review plan</h3>
                      <p>
                        Get a short set of review activities based on the questions
                        you missed.
                      </p>
                    </div>
                    {!studyPlan && (
                      <button
                        className="primary-button quiz-primary-button"
                        type="button"
                        onClick={handleGenerateStudyPlan}
                        disabled={planLoading}
                      >
                        {planLoading ? "Creating plan…" : "Create review plan"}
                      </button>
                    )}
                  </div>
                  {error && <p className="quiz-error" role="alert">{error}</p>}
                  {planLoading && (
                    <p className="quiz-loading" role="status">
                      <span className="loading-spinner" />
                      Your AI tutor is preparing focused review steps.
                    </p>
                  )}
                  {studyPlan && (
                    <ol className="study-plan-list">
                      {studyPlan.steps.map((step, index) => (
                        <li className="study-plan-step" key={`${index}-${step.focus}`}>
                          <span className="study-plan-number">{index + 1}</span>
                          <div>
                            <strong>{step.focus}</strong>
                            <p>{step.activity}</p>
                          </div>
                          <span className="study-plan-duration">{step.minutes} min</span>
                        </li>
                      ))}
                    </ol>
                  )}
                </section>
              )}
              <div className="quiz-submit-row">
                <span>Your result was calculated by the backend.</span>
                <button
                  className="primary-button quiz-primary-button"
                  type="button"
                  onClick={resetQuiz}
                  disabled={planLoading}
                >
                  Try another quiz
                </button>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

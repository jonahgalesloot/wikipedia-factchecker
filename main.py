import tkinter as tk
from tkinter import scrolledtext
import ollama
import wikipediaapi
import wikipedia
import re
import time

num_articles = 3
analysis_ai_model = "bespoke-minicheck"
summary_ai_model = "bespoke-minicheck"

def search_wikipedia(query, num_articles=3):
    """Search Wikipedia for relevant articles and return a list of dicts with title and summary."""
    print(f"Searching Wikipedia for: {query}")
    user_agent = "AI_Factchecker/1.0 (contact: your-email@example.com)"  # Replace with your actual details
    wiki_api = wikipediaapi.Wikipedia(user_agent=user_agent, language='en')
    
    # Use the wikipedia package's search to get matching page titles.
    search_results = wikipedia.search(query, results=num_articles)
    articles = []
    if not search_results:
        print("No Wikipedia search results found.")
        return articles

    for result in search_results:
        page = wiki_api.page(result)
        if page.exists():
            articles.append({"title": page.title, "summary": page.summary})
            print(f"Article added: {page.title}")
    if not articles:
        print("No valid Wikipedia articles found.")
    return articles

def check_statement():
    global analysis_ai_model, summary_ai_model
    """Process each article individually, print full analysis to console, then combine reports via a second AI prompt."""
    total_start_time = time.time()
    process_start_times = []
    process_end_times = []
    print("Starting AI Fact Checker...")
    statement_text = statement_input.get().strip()
    if not statement_text:
        display_result("Please enter a statement to verify.", error=True)
        return

    # Determine source: manual input or Wikipedia search.
    if manual_input_visible:
        document_text = document_input.get("1.0", tk.END).strip()
        print("Using manually entered document.")
        if not document_text:
            display_result("Please enter a document or use Wikipedia search.", error=True)
            return
        articles = [{"title": "Manual Input", "summary": document_text}]
    else:
        print("Using Wikipedia search for document...")
        articles = search_wikipedia(statement_text, num_articles)
        if not articles:
            display_result("No relevant Wikipedia articles found.", error=True)
            return

    # Process each article individually.
    individual_analyses = []
    combined_certainties = []
    article_results = ""
    for index, article in enumerate(articles):
        # Refined prompt with explicit markers and clear instructions.
        process_start_times.append(time.time())
        prompt = f"""Using the following Wikipedia article information:

Title: {article['title']}
Summary: {article['summary']}

Evaluate the veracity of the following statement: "{statement_text}"

Please provide your analysis in the following structured format EXACTLY as shown, including the markers. Do not deviate from this structure:

[START_RESPONSE]
Result: [Concise phrase, max 3 words]
Certainty: [Provide a precise percentage between 0-100%, avoiding round numbers. Consider nuances and counterpoints.]
Key Quotes:
- [Supporting Quote 1] [Source: {article['title']}]
- [Supporting Quote 2] [Source: {article['title']}]
- [Include contradicting quotes or points ONLY if relevant. If not applicable, omit the counterpoint section.]
Explanation: [Provide a detailed explanation of your decision. Address nuances, potential biases, and limitations of the information. Explain how you arrived at the certainty percentage, considering both supporting evidence and any counterpoints if present.]
[END_RESPONSE]

Remember:
1. Use EXACT formatting as shown above, including all sections and markers.
2. The Result should be a concise phrase of no more than 3 words (e.g., "Mostly True", "Partially Incorrect", "Highly Accurate").
3. Provide a precise certainty percentage (e.g., 73.5%, 88.2%), avoiding round numbers.
4. When providing a certainty percentage, go to the nearest tenth (e.g., 73.5% instead of 73%)
5. NEVER give 100% or 0% for certainty, and only give above 90% or below 10% in cases where no counterpoints are found.
5. Include supporting quotes always. Include counterpoints only if relevant to the statement's evaluation.
6. Ensure your explanation is comprehensive, addressing all aspects of the statement.
7. If information is lacking or ambiguous, reflect this in your certainty percentage and explanation.
"""

        print(f"Sending request to Bespoke Minicheck AI for article: {article['title']}")
        try:
            response = ollama.chat(model=analysis_ai_model, messages=[{"role": "user", "content": prompt}])
            result_content = response["message"]["content"]
            print(f"AI Response for {article['title']}:\n{result_content}\n")
            parsed = parse_ai_response(result_content)
            if parsed is None:
                print(f"Failed to parse response for article: {article['title']}")
                continue
            try:
                cert_value = float(parsed['certainty'].replace('%', '').strip())
                combined_certainties.append(cert_value)
            except Exception as e:
                print(f"Error parsing certainty for article {article['title']}: {e}")
            analysis_text = (f"Article: {article['title']}\n"
                             f"Result: {parsed['result']}\n"
                             f"Certainty: {parsed['certainty']}\n"
                             f"Key Quotes:\n" + "\n".join(parsed['key_quotes']) + "\n"
                             f"Explanation: {parsed['explanation']}\n")
            individual_analyses.append(analysis_text)
            article_results += "---\n" + analysis_text + "\n"
        except Exception as e:
            print(f"Error for article {article['title']}: {e}")
            
        process_end_times.append(time.time())

    # Print all individual analyses to the console.
    print("Individual Analyses:")
    for analysis in individual_analyses:
        print(analysis)
        print("-----")

    if combined_certainties:
        avg_certainty = sum(combined_certainties) / len(combined_certainties)
    else:
        avg_certainty = 0

    # Create a combined prompt to ask the AI to merge the individual analyses.
    combined_prompt = "The following are individual fact-check analyses for the same statement from multiple Wikipedia articles:\n\n"
    for analysis in individual_analyses:
        combined_prompt += analysis + "\n---\n"
    combined_prompt += """
Now, based on all the individual article analyses, please provide a final combined summary report. Use the following format EXACTLY, including the markers:

[START_FINAL]
Combined Result: [Concise phrase, max 3 words]
Average Certainty: [Precise percentage between 0-100%, calculated from individual certainties]
Combined Key Quotes:
- [Most relevant quote 1] [Source: Article Title]
- [Most relevant quote 2] [Source: Article Title]
- [Additional quotes as needed, prioritizing the most impactful]
- [Most relevant counterpoint 1] [Source: Article Title]
- [Most relevant counterpoint 2] [Source: Article Title]
- [If no significant counterpoints were found across all articles, omit this counterpoint section."]
Final Explanation: [Provide a comprehensive explanation that synthesizes information from all articles. Address:
1. The overall consensus or disagreement among sources
2. Any nuances or complexities in evaluating the statement
3. Potential limitations or biases in the available information
4. Justification for the combined result and certainty percentage
5. The relative weight given to different sources or pieces of information]
[END_FINAL]

Remember:
1. Use EXACT formatting as shown above, including all sections and markers.
2. The Combined Result should be a concise phrase of no more than 3 words that best summarizes the overall evaluation.
3. Calculate and provide a precise Average Certainty percentage, avoiding round numbers.
4. Include the most relevant and impactful quotes and counterpoints from across all analyzed articles.
5. In the Final Explanation, synthesize information from all sources to provide a comprehensive evaluation of the statement's veracity.
6. If information is lacking or contradictory across sources, reflect this in your Combined Result, Average Certainty, and Final Explanation.
"""

    print("Sending combined prompt for final summary...")
    try:
        final_response = ollama.chat(model=summary_ai_model, messages=[{"role": "user", "content": combined_prompt}])
        final_result = final_response["message"]["content"]
        print("Final Combined AI Response:\n", final_result)
        final_parsed = parse_final_response(final_result, avg_certainty)
    except Exception as e:
        final_parsed = None
        print(f"Error during final summary: {e}")

    if final_parsed:
        final_report = (f"Final Combined Report:\n"
                        f"Combined Result: {final_parsed['combined_result']}\n"
                        f"Average Certainty: {final_parsed['average_certainty']}\n"
                        f"Combined Key Quotes:\n" + "\n".join(final_parsed['combined_key_quotes']) + "\n"
                        f"Final Explanation: {final_parsed['final_explanation']}\n\n")
    else:
        final_report = "Failed to generate final combined report.\n\n"

    complete_report = final_report + "Detailed Individual Analyses:\n" + article_results

    # Calculate and print processing times
    total_end_time = time.time()
    total_processing_time = total_end_time - total_start_time
    print(f"Total processing time: {total_processing_time:.2f} seconds")
    complete_report += f"\nTotal processing time: {total_processing_time:.2f} seconds\n"

    for i, (start, end) in enumerate(zip(process_start_times, process_end_times)):
        article_processing_time = end - start
        print(f"Processing time for article {i + 1}: {article_processing_time:.2f} seconds")
        complete_report += f"Processing time for article {i + 1}: {article_processing_time:.2f} seconds\n"

    display_result(complete_report)

def parse_ai_response(response_text):
    """
    Parses the AI response using markers [START_RESPONSE] and [END_RESPONSE].
    Returns a dictionary with keys: result, certainty, key_quotes (list), explanation.
    """
    try:
        start_marker = "[START_RESPONSE]"
        end_marker = "[END_RESPONSE]"
        response_upper = response_text.upper()
        start_index = response_upper.find(start_marker)
        end_index = response_upper.find(end_marker)
        if start_index == -1 or end_index == -1:
            print("Markers not found in AI response.")
            return None
        content = response_text[start_index + len(start_marker):end_index].strip()
        print("Extracted AI content:\n", content)

        result_match = re.search(r"Result:\s*(.*)", content)
        certainty_match = re.search(r"Certainty:\s*(.*)", content)
        key_quotes_match = re.search(r"Key Quotes:\s*(.*?)Explanation:", content, re.DOTALL)
        explanation_match = re.search(r"Explanation:\s*(.*)", content, re.DOTALL)

        if not result_match or not certainty_match or not key_quotes_match or not explanation_match:
            print("One or more expected fields not found in AI response content.")
            return None

        result = result_match.group(1).strip()
        certainty = certainty_match.group(1).strip()
        key_quotes_raw = key_quotes_match.group(1).strip().split('\n')
        key_quotes = [line.strip() for line in key_quotes_raw if line.strip()]
        explanation = explanation_match.group(1).strip()

        return {
            "result": result,
            "certainty": certainty,
            "key_quotes": key_quotes,
            "explanation": explanation
        }
    except Exception as e:
        print(f"Exception in parse_ai_response: {e}")
        return None

def parse_final_response(response_text, average_certainty=None):
    """
    Parses the final combined AI response using markers [START_FINAL] and [END_FINAL].
    Returns a dictionary with keys: combined_result, average_certainty, combined_key_quotes (list), final_explanation.
    """
    try:
        start_marker = "[START_FINAL]"
        end_marker = "[END_FINAL]"
        response_upper = response_text.upper()
        start_index = response_upper.find(start_marker)
        end_index = response_upper.find(end_marker)
        if start_index == -1 or end_index == -1:
            print("Final markers not found in AI response.")
            return None
        content = response_text[start_index + len(start_marker):end_index].strip()
        print("Extracted final AI content:\n", content)

        result_match = re.search(r"Combined Result:\s*(.*)", content)
        if average_certainty is None:
            certainty_match = re.search(r"Average Certainty:\s*(.*)", content)
            if certainty_match:
                average_certainty = certainty_match.group(1).strip()
        else:
            average_certainty = f"{average_certainty:.1f}%"
        
        key_quotes_match = re.search(r"Combined Key Quotes:\s*(.*?)(?:Counterpoints:|Final Explanation:)", content, re.DOTALL)
        counterpoints_match = re.search(r"Counterpoints:\s*(.*?)Final Explanation:", content, re.DOTALL)
        explanation_match = re.search(r"Final Explanation:\s*(.*)", content, re.DOTALL)

        if not result_match or not key_quotes_match or not explanation_match:
            print("One or more expected fields not found in final AI response content.")
            return None

        combined_result = result_match.group(1).strip()
        key_quotes_raw = key_quotes_match.group(1).strip().split('\n')
        combined_key_quotes = [line.strip() for line in key_quotes_raw if line.strip()]
        
        counterpoints = []
        if counterpoints_match:
            counterpoints_raw = counterpoints_match.group(1).strip().split('\n')
            counterpoints = [line.strip() for line in counterpoints_raw if line.strip()]
        
        final_explanation = explanation_match.group(1).strip()

        return {
            "combined_result": combined_result,
            "average_certainty": average_certainty,
            "combined_key_quotes": combined_key_quotes,
            "counterpoints": counterpoints,
            "final_explanation": final_explanation
        }
    except Exception as e:
        print(f"Exception in parse_final_response: {e}")
        return None

def display_result(result_text, error=False):
    """Displays the result in the result text box."""
    result_display.config(state=tk.NORMAL)
    result_display.delete(1.0, tk.END)
    result_display.insert(tk.END, result_text)
    result_display.config(state=tk.DISABLED)
    print("Displaying result to user.")

def toggle_manual_input():
    """Toggles between Wikipedia search and manual document input."""
    global manual_input_visible
    manual_input_visible = not manual_input_visible
    if manual_input_visible:
        document_frame.pack(pady=5)
        toggle_button.config(text="Use Wikipedia Search")
        print("Switched to Manual Input mode.")
    else:
        document_frame.pack_forget()
        toggle_button.config(text="Use Manual Input")
        print("Switched to Wikipedia Search mode.")

# --- Tkinter GUI Setup ---
root = tk.Tk()
root.title("AI Fact Checker")
root.geometry("600x700")

tk.Label(root, text="Enter the statement to verify:").pack()
statement_input = tk.Entry(root, width=70)
statement_input.pack(pady=5)

manual_input_visible = False
toggle_button = tk.Button(root, text="Use Manual Input", command=toggle_manual_input)
toggle_button.pack(pady=5)

document_frame = tk.Frame(root)
tk.Label(document_frame, text="Enter the source document:").pack()
document_input = scrolledtext.ScrolledText(document_frame, height=10, width=70, wrap=tk.WORD)
document_input.pack()

verify_button = tk.Button(root, text="Check Truthfulness", command=check_statement)
verify_button.pack(pady=10)

result_display = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=60, height=20)
result_display.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
result_display.insert(tk.END, "Result will appear here.")
result_display.config(state=tk.DISABLED)

root.mainloop()

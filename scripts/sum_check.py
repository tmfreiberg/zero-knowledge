from sympy import symbols, Poly, isprime, sympify
from sympy.polys.domains import GF
from itertools import product
from typing import Optional, Union, List, Dict, Tuple
from sympy.polys.domains.modularinteger import ModularInteger
from sympy.polys.domains.finitefield import FiniteField
import random
from utils import print_header, display_aligned
import re

def sum_check_choose_poly() -> Union[None, Tuple[Dict[int, Poly], Dict[int, Union[int, ModularInteger]], Dict[int, Union[int, ModularInteger]], List[ModularInteger]]]:
    """
    Initiates the sum-check protocol by prompting the user for inputs.

    This function asks the user to input a prime number `p` to define the finite field GF(p),
    and a polynomial `g` over that field. It also asks whether the protocol should be interactive.
    It then constructs the polynomial and calls `sum_check_protocol` to perform the sum-check protocol.

    Returns:
        A tuple containing:
            - univariate (Dict[int, Poly]): Univariate polynomials at each round.
            - rand_eval (Dict[int, Union[int, ModularInteger]]): Evaluations at random points.
            - sum_check (Dict[int, Union[int, ModularInteger]]): Sum-check values at each round.
            - rand (List[ModularInteger]): List of random field elements used in the protocol.

        Returns None if the input prime is invalid.
    """
    # Prompt the user to input a prime number
    p = input("Enter a prime:")
    p = int(p)
    if not isprime(p):
        print("Invalid input: p must be prime. We'll modify the function to handle fields of prime-power order later.")
        return None

    # Define the finite field GF(p)
    F = GF(p)

    # Input polynomial as a string
    poly_str = input("Enter your polynomial (e.g. 2*X_0**2 + X_0*X_1*X_2 + X_1*X_4**3 + X_1 + X_3):")

    # Determine if the protocol should be interactive
    interactive = input("Do you want this to be interactive? (y/n)")
    if interactive.lower() == 'y':
        user_input = True
    else:
        user_input = False

    # Extract variable names from the polynomial string
    variable_names = sorted(set(re.findall(r'X_\d+', poly_str)))
    # Define symbols for variables
    variables = symbols(variable_names)
    variable_map = {name: var for name, var in zip(variable_names, variables)}
    # Convert the string to a SymPy expression
    poly_expr = sympify(poly_str, locals=variable_map)
    # Define the polynomial over the finite field
    g = Poly(poly_expr, variables, domain=F)

    # Call the sum-check protocol
    return sum_check_protocol(g=g, user_input=user_input)


def sum_check_protocol(
    g: Poly,
    user_input: bool = False
) -> Union[None, Tuple[Dict[int, Poly], Dict[int, Union[int, ModularInteger]], Dict[int, Union[int, ModularInteger]], List[ModularInteger]]]:
    """
    Performs the sum-check protocol on the given polynomial.

    Args:
        g (Poly): The polynomial over GF(p) on which to perform the sum-check protocol.
        user_input (bool): Whether to prompt the user for input during the protocol.

    Returns:
        A tuple containing:
            - univariate (Dict[int, Poly]): Univariate polynomials at each round.
            - rand_eval (Dict[int, Union[int, ModularInteger]]): Evaluations at random points.
            - sum_check (Dict[int, Union[int, ModularInteger]]): Sum-check values at each round.
            - rand (List[ModularInteger]): List of random field elements used in the protocol.

        Returns None if the field is not of prime order.
    """
    X = g.gens  # Tuple of variables in the polynomial
    v = len(X)  # Number of variables
    F = g.domain  # The finite field GF(p)

    if not isprime(F.mod):
        print("F must be of prime order: we'll modify the function to handle fields of prime-power order later.")
        return None

    # Compute H = sum of g evaluated over all boolean assignments
    H = sum(g.eval({X[k]: b_k for k, b_k in enumerate(b)}) for b in product([0, 1], repeat=v))

    # Initialize data structures
    rand: List[ModularInteger] = []  # List of random field elements
    univariate: Dict[int, Poly] = {}  # Univariate polynomials at each round
    rand_eval: Dict[int, Union[int, ModularInteger]] = {}  # Evaluations at random points
    sum_check: Dict[int, Union[int, ModularInteger]] = {}  # Sum-check values at each round

    for j in range(v + 1):
        if j < v:
            print_header(f"Round {j}")
        if j == v:
            print_header(f"Final check")

        if j == 0:
            univariate[j] = g  # Initial polynomial
        if j > 0:
            # Generate random field element
            rfe = random_field_element(field=F, user_input=user_input)
            if rfe is None:
                print_header("Protocol terminated")
                break
            # Append random field element to the list
            rand.append(rfe)
            # Evaluate previous univariate polynomial at the random point
            rand_eval[j - 1] = univariate[j - 1].eval({X[j - 1]: rand[j - 1]}) % F.mod
            # Substitute the first j random field elements into the polynomial
            univariate[j] = g.subs({X[i]: rand[i] for i in range(j)})

        if j < v:
            # Compute the univariate polynomial for the current round
            univariate[j] = sum(
                univariate[j].subs({X[k + j + 1]: b_k for k, b_k in enumerate(b)})
                for b in product([0, 1], repeat=v - 1 - j)
            )
            # Compute the sum-check value
            sum_check[j] = (univariate[j].eval({X[j]: 0}) + univariate[j].eval({X[j]: 1})) % F.mod
        else:
            # Final round: evaluate the last polynomial at the random point
            rand_eval[j] = univariate[j - 1].eval({X[j - 1]: rand[j - 1]}) % F.mod
            # Sum-check value from the oracle
            sum_check[j] = g.subs({X[i]: r for i, r in enumerate(rand)}) % F.mod

        # Perform consistency checks
        consistency_check(
            j=j,
            v=v,
            X=X,
            H=H,
            rand=rand,
            univariate=univariate,
            rand_eval=rand_eval,
            sum_check=sum_check
        )

    return univariate, rand_eval, sum_check, rand


def consistency_check(
    j: int,
    v: int,
    X: Tuple[symbols],
    H: int,
    rand: List[ModularInteger],
    univariate: Dict[int, Poly],
    rand_eval: Dict[int, Union[int, ModularInteger]],
    sum_check: Dict[int, Union[int, ModularInteger]]
) -> None:
    """
    Performs the consistency checks for each round of the sum-check protocol.

    Args:
        j (int): The current round index.
        v (int): The total number of variables.
        X (Tuple[symbols]): Tuple of variables in the polynomial.
        H (int): The sum of the polynomial evaluated over all boolean assignments.
        rand (List[ModularInteger]): List of random field elements chosen so far.
        univariate (Dict[int, Poly]): Univariate polynomials at each round.
        rand_eval (Dict[int, Union[int, ModularInteger]]): Evaluations at random points.
        sum_check (Dict[int, Union[int, ModularInteger]]): Sum-check values at each round.

    Returns:
        None
    """
    if j < v:
        # Prepare variable names for display
        fix_rand = [str(int(r)) for r in rand[:j]]
        bool_var = [f'b_{k}' for k in range(j + 1, v)]
        poly_input = ', '.join(fix_rand + [str(X[j])] + bool_var)

    if j > 0:
        # Verifier sends a random field element to the prover
        print(
            f"V sends {int(rand[j - 1])}, chosen uniformly at random from F, independently of any previous choices, to P."
        )

    if j < v:
        print(f"\nP sends the following univariate polynomial to V:\n")

    if j < v - 1:
        equation_1 = f"\ng_{j}({X[j]}) = sum g({poly_input}) over {', '.join(bool_var)} in {{0,1}}^{len(bool_var)}"
    elif j == v - 1:
        equation_1 = f"\ng_{j}({X[j]}) = g({poly_input})"

    if j < v:
        equation_2 = f"= {univariate[j].as_expr()}"
        display_aligned(equation_1, equation_2)

    # Perform checks depending on the round
    if j == 0:
        # Initial check: verify that H equals g_0(0) + g_0(1)
        bool_hypercube = ', '.join([f'b_{k}' for k in range(v)])
        print(
            f"\nV checks that H = g_{j}(0) + g_{j}(1), where H is sum of g({bool_hypercube}) over {bool_hypercube} in {{0,1}}^{v}, according to P.\n"
        )
        equation_1 = f"H = {H}"
        check_passed = H == sum_check[j]
    elif 0 < j < v:
        # Verify that g_{j-1}(r_{j-1}) equals g_j(0) + g_j(1)
        print(
            f"\nV compares two most recent polynomials by checking that g_{j - 1}({int(rand[j - 1])}) = g_{j}(0) + g_{j}(1):\n"
        )
        equation_1 = f"g_{j - 1}({int(rand[j - 1])}) = {rand_eval[j - 1]}"
        check_passed = rand_eval[j - 1] == sum_check[j]
    elif j == v:
        # Final check: verify that g_{v-1}(r_{v-1}) equals g evaluated at all random points
        random_tuple = ', '.join([str(int(r)) for r in rand])
        print(f"\nV checks that g_{j - 1}({int(rand[j - 1])}) = g({random_tuple}) (the RHS given P, assuming P committed to g at the outset, or an oracle):\n")
        equation_1 = f"g_{j - 1}({int(rand[j - 1])}) = {rand_eval[j]}"
        equation_2 = f"g({random_tuple}) = {sum_check[j]}"
        display_aligned(equation_1, equation_2)
        check_passed = rand_eval[j] == sum_check[j]

    if j < v:
        equation_2 = f"g_{j}(0) + g_{j}(1) = {sum_check[j]}"
        display_aligned(equation_1, equation_2)

    if check_passed:
        if j == v:
            print("\nFINAL CHECK PASSED: ACCEPT")
        else:
            print("\nCHECK PASSED")
    else:
        print("\nCHECK FAILED: REJECT")


"""ANCILLARY FUNCTIONS"""

def random_field_element(
    field: FiniteField,
    user_input: bool = False,
    max_attempts: Optional[int] = None
) -> Optional[ModularInteger]:
    """
    Generates a random element from the finite field.

    Args:
        field (FiniteField): The finite field GF(p).
        user_input (bool): If True, prompts the user to input the element.
        max_attempts (Optional[int]): Maximum number of attempts for user input.

    Returns:
        A random field element, or None if user cancels.
    """
    if user_input:
        user_response = input_random_field_element(max_attempts=max_attempts)
        if isinstance(user_response, int):
            return field(user_response)
        else:
            return None
    # Generate a random integer between 0 and p - 1
    return field(random.randint(0, field.mod - 1))


def input_random_field_element(max_attempts: Optional[int] = None) -> Optional[int]:
    """
    Prompts the user to input an integer element from the field.

    Args:
        max_attempts (Optional[int]): Maximum number of attempts allowed.

    Returns:
        The integer entered by the user, or None if cancelled or attempts exhausted.
    """
    attempts = 0 if max_attempts is not None else None
    prompt = "\nEnter c to cancel or select element uniformly at random from field, independent of any previous selection:"

    while attempts is None or (attempts != max_attempts):
        response = input(prompt)
        if response == 'c':
            return None
        try:
            response_int = int(response)
            return response_int
        except ValueError:
            if attempts is not None:
                attempts += 1
                if attempts == max_attempts:
                    print("\nInvalid input. No more attempts.")
                    return None
                elif attempts == max_attempts - 1:
                    prompt = "\nInvalid input. Final attempt: enter an integer, or c to cancel:"
                else:
                    prompt = "\nInvalid input. Enter an integer, or c to cancel:"
            else:
                prompt = "\nInvalid input. Enter an integer, or c to cancel:"

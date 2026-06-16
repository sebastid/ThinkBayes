"""World Cup Football Predictor using Bayesian inference.

This module implements a Bayesian model for predicting football match outcomes
using historical team performance data.

The model estimates each team's strength (goal-scoring ability) using observed
match results, then predicts future match probabilities.

Example:
    >>> predictor = WorldCupPredictor()
    >>> predictor.AddMatch('Brazil', 'France', 3, 1)
    >>> predictor.AddMatch('Germany', 'Spain', 1, 1)
    >>> prob_brazil = predictor.PredictWin('Brazil', 'Argentina')
    >>> print(f'Brazil wins: {prob_brazil:.1%}')
"""

import thinkbayes
import math


class TeamStrength(thinkbayes.Suite):
    """Represents hypotheses about a team's goal-scoring strength.

    In football, the number of goals scored typically follows a Poisson
    distribution. The rate parameter (lambda) represents expected goals per game.

    We use a Gamma distribution as the prior (conjugate prior for Poisson).
    """

    def Likelihood(self, data, hypo):
        """Computes likelihood of observed goals given team strength.

        Args:
            data: int, number of goals scored by the team
            hypo: float, expected goals per game (lambda parameter)

        Returns:
            float, likelihood = (lambda^k * e^-lambda) / k!
                where k = number of goals
        """
        lam = hypo
        k = data

        # Poisson likelihood: P(k goals | lambda) = (lambda^k * e^-lambda) / k!
        # We can omit the k! since it's constant across hypotheses
        if lam == 0:
            return 0 if k > 0 else 1

        return math.exp(k * math.log(lam) - lam)


class FootballMatch:
    """Represents a football match result."""

    def __init__(self, team1, team2, goals1, goals2):
        """Initialize a match.

        Args:
            team1: str, name of first team
            team2: str, name of second team
            goals1: int, goals scored by team1
            goals2: int, goals scored by team2
        """
        self.team1 = team1
        self.team2 = team2
        self.goals1 = goals1
        self.goals2 = goals2

    def __repr__(self):
        return f'{self.team1} {self.goals1}-{self.goals2} {self.team2}'


class WorldCupPredictor:
    """Predicts football match outcomes using Bayesian inference.

    For each team, maintains a posterior distribution over expected goals per game.
    Uses historical match data to update team strength estimates.
    """

    def __init__(self, prior_mean=1.5, prior_variance=0.8):
        """Initialize the predictor with prior distributions.

        Args:
            prior_mean: float, prior expected goals per game
            prior_variance: float, variance of prior belief

        The prior uses a Gamma distribution (conjugate for Poisson).
        Gamma parameters derived from mean and variance:
            alpha = mean^2 / variance
            beta = mean / variance
        """
        # Gamma parameters: alpha = mean^2/variance, beta = mean/variance
        self.prior_alpha = prior_mean ** 2 / prior_variance
        self.prior_beta = prior_mean / prior_variance

        self.teams = {}  # team_name -> TeamStrength suite
        self.matches = []  # history of matches

        print('World Cup Predictor initialized')
        print(f'Prior: mean={prior_mean:.2f}, variance={prior_variance:.2f}')
        print(f'Gamma distribution: alpha={self.prior_alpha:.2f}, beta={self.prior_beta:.2f}')

    def _GetTeamSuite(self, team_name):
        """Get or create team strength distribution.

        Args:
            team_name: str, team name

        Returns:
            TeamStrength suite with prior over expected goals
        """
        if team_name not in self.teams:
            # Create prior: Gamma distribution discretized to values 0.1 to 4.0
            hypos = [lam/10.0 for lam in range(1, 41)]  # 0.1 to 4.0 goals

            suite = TeamStrength(hypos, name=team_name)

            # Set prior probabilities based on Gamma distribution
            for lam in hypos:
                # Gamma pdf: (beta^alpha / Gamma(alpha)) * lam^(alpha-1) * exp(-beta*lam)
                # Simplified: we just use relative probabilities
                alpha = self.prior_alpha
                beta = self.prior_beta
                prior_prob = (lam ** (alpha - 1)) * math.exp(-beta * lam)
                suite.Set(lam, prior_prob)

            suite.Normalize()
            self.teams[team_name] = suite

        return self.teams[team_name]

    def AddMatch(self, team1, team2, goals1, goals2):
        """Update team strength distributions based on match result.

        Args:
            team1: str, name of first team
            team2: str, name of second team
            goals1: int, goals scored by team1
            goals2: int, goals scored by team2
        """
        match = FootballMatch(team1, team2, goals1, goals2)
        self.matches.append(match)

        # Update each team's strength based on their goal count
        suite1 = self._GetTeamSuite(team1)
        suite2 = self._GetTeamSuite(team2)

        suite1.Update(goals1)
        suite2.Update(goals2)

        print(f'Updated: {match}')

    def GetTeamStats(self, team_name):
        """Get posterior statistics for a team.

        Args:
            team_name: str, team name

        Returns:
            dict with Mean, Median, Std, and Credible Interval
        """
        suite = self._GetTeamSuite(team_name)

        return {
            'Mean': suite.Mean(),
            'Median': thinkbayes.Percentile(suite, 50),
            'StdDev': math.sqrt(suite.Var()),
            'CI90': thinkbayes.CredibleInterval(suite, 90),
        }

    def PrintTeamStats(self, team_name):
        """Print posterior statistics for a team.

        Args:
            team_name: str, team name
        """
        stats = self.GetTeamStats(team_name)
        print(f'\n{team_name}:')
        print(f'  Expected goals per game: {stats["Mean"]:.2f}')
        print(f'  Median: {stats["Median"]:.2f}')
        print(f'  Std Dev: {stats["StdDev"]:.2f}')
        ci_low, ci_high = stats['CI90']
        print(f'  90% Credible Interval: [{ci_low:.2f}, {ci_high:.2f}]')

    def _PoissonProbability(self, lam, k):
        """Compute Poisson probability P(k events | rate=lam).

        Args:
            lam: float, rate parameter (expected value)
            k: int, number of events

        Returns:
            float, probability
        """
        if lam == 0:
            return 1.0 if k == 0 else 0.0
        return math.exp(k * math.log(lam) - lam)

    def PredictMatch(self, team1, team2, max_goals=5):
        """Predict probabilities for all possible match outcomes.

        Marginalizes over team strength distributions to compute probability
        of each possible final score.

        Args:
            team1: str, name of first team
            team2: str, name of second team
            max_goals: int, maximum goals to consider for each team

        Returns:
            dict mapping (goals1, goals2) tuples to probabilities
        """
        suite1 = self._GetTeamSuite(team1)
        suite2 = self._GetTeamSuite(team2)

        # Marginalize over team strengths
        # P(goals1, goals2) = integral over lam1, lam2 of:
        #   P(goals1|lam1) * P(goals2|lam2) * P(lam1) * P(lam2)

        predictions = {}
        total_prob = 0

        for k1 in range(max_goals + 1):
            for k2 in range(max_goals + 1):
                prob = 0

                # Sum over all hypotheses about team strengths
                for lam1, p_lam1 in suite1.Items():
                    for lam2, p_lam2 in suite2.Items():
                        # Joint probability of goals given strengths
                        p_goals = (self._PoissonProbability(lam1, k1) *
                                 self._PoissonProbability(lam2, k2))
                        # Marginal: weight by posterior of strengths
                        prob += p_lam1 * p_lam2 * p_goals

                predictions[(k1, k2)] = prob
                total_prob += prob

        # Normalize
        if total_prob > 0:
            for key in predictions:
                predictions[key] /= total_prob

        return predictions

    def PrintMatchPrediction(self, team1, team2, max_goals=4):
        """Print predicted probabilities for match outcomes.

        Args:
            team1: str, name of first team
            team2: str, name of second team
            max_goals: int, maximum goals to show
        """
        predictions = self.PredictMatch(team1, team2, max_goals)

        print(f'\nMatch prediction: {team1} vs {team2}')
        print('-' * 50)
        print(f'{"Score":<20} {"Probability":<15}')
        print('-' * 50)

        # Sort by probability
        sorted_pred = sorted(predictions.items(),
                           key=lambda x: x[1], reverse=True)

        for (k1, k2), prob in sorted_pred:
            if prob > 0.01:  # Only show probabilities > 1%
                score = f'{team1} {k1}-{k2} {team2}'
                print(f'{score:<20} {prob:>6.1%}')

    def PredictWin(self, team1, team2, max_goals=5):
        """Predict probability that team1 wins.

        Args:
            team1: str, name of team we're predicting for
            team2: str, name of opponent
            max_goals: int, maximum goals to consider

        Returns:
            float, probability team1 wins (0 to 1)
        """
        predictions = self.PredictMatch(team1, team2, max_goals)

        win_prob = 0
        for (k1, k2), prob in predictions.items():
            if k1 > k2:
                win_prob += prob

        return win_prob

    def PredictDraw(self, team1, team2, max_goals=5):
        """Predict probability of draw.

        Args:
            team1: str, name of first team
            team2: str, name of second team
            max_goals: int, maximum goals to consider

        Returns:
            float, probability of draw (0 to 1)
        """
        predictions = self.PredictMatch(team1, team2, max_goals)

        draw_prob = 0
        for (k1, k2), prob in predictions.items():
            if k1 == k2:
                draw_prob += prob

        return draw_prob

    def PredictLoss(self, team1, team2, max_goals=5):
        """Predict probability that team1 loses.

        Args:
            team1: str, name of team we're predicting for
            team2: str, name of opponent
            max_goals: int, maximum goals to consider

        Returns:
            float, probability team1 loses (0 to 1)
        """
        predictions = self.PredictMatch(team1, team2, max_goals)

        loss_prob = 0
        for (k1, k2), prob in predictions.items():
            if k1 < k2:
                loss_prob += prob

        return loss_prob

    def PrintMatchSummary(self, team1, team2):
        """Print summary of match prediction.

        Args:
            team1: str, name of first team
            team2: str, name of second team
        """
        win_prob = self.PredictWin(team1, team2)
        draw_prob = self.PredictDraw(team1, team2)
        loss_prob = self.PredictLoss(team1, team2)

        print(f'\n{team1} vs {team2}:')
        print(f'  {team1} wins:  {win_prob:>6.1%}')
        print(f'  Draw:      {draw_prob:>6.1%}')
        print(f'  {team2} wins:  {loss_prob:>6.1%}')


def main():
    """Example: Predict World Cup matches using historical data."""

    predictor = WorldCupPredictor(prior_mean=1.4, prior_variance=0.7)

    # Simulate some group stage matches (fictional data for demonstration)
    print('\n--- Adding match results ---')
    predictor.AddMatch('Brazil', 'Serbia', 2, 0)
    predictor.AddMatch('Brazil', 'Switzerland', 1, 1)
    predictor.AddMatch('Germany', 'Spain', 1, 1)
    predictor.AddMatch('Germany', 'Japan', 2, 1)
    predictor.AddMatch('France', 'Australia', 4, 1)
    predictor.AddMatch('France', 'Denmark', 2, 1)
    predictor.AddMatch('Argentina', 'Saudi Arabia', 1, 2)
    predictor.AddMatch('Argentina', 'Mexico', 2, 0)

    # Print team statistics
    print('\n--- Team Strength Estimates ---')
    for team in ['Brazil', 'Germany', 'France', 'Argentina']:
        predictor.PrintTeamStats(team)

    # Predict knockout stage matches
    print('\n--- Match Predictions ---')
    predictor.PrintMatchPrediction('Brazil', 'France')
    predictor.PrintMatchSummary('Brazil', 'France')

    predictor.PrintMatchPrediction('Germany', 'Argentina')
    predictor.PrintMatchSummary('Germany', 'Argentina')

    # Predict semifinals
    print('\n--- More Predictions ---')
    predictor.PrintMatchSummary('Brazil', 'Germany')
    predictor.PrintMatchSummary('France', 'Argentina')


if __name__ == '__main__':
    main()

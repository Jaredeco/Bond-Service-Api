from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, CreateAPIView, RetrieveUpdateDestroyAPIView
from base.models import Bond, Investment
from .serializers import BondSerializer, UserSerializer, InvestmentSerializer
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from django.db.models import Avg
from django.utils import timezone


class BondListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = Bond.objects.all()
    serializer_class = BondSerializer


class BondCRUDView(RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = Bond.objects.all()
    serializer_class = BondSerializer
    lookup_field = 'isin'


class BondCreateView(CreateAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = Bond.objects.all()
    serializer_class = BondSerializer


class UsersListView(ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAdminUser,)


class AnalyzePortfolioView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, username):
        investments = Investment.objects.filter(username=username)
        if len(investments) == 0:
            return Response(status=status.HTTP_204_NO_CONTENT)
        average_interest_rate = investments.aggregate(avg=Avg('bond_isin__interest_rate'))['avg']
        soon_expires = investments.order_by('bond_isin__expiration_date').first()
        portfolio_balance = 0
        future_portfolio_balance = 0
        today = timezone.now()
        for investment in investments:
            portfolio_balance += investment.volume * investment.bond_isin.value
            if investment.bond_isin.expiration_date >= today:
                future_portfolio_balance += investment.volume * (investment.bond_isin.value + (investment.bond_isin.
                                                                                               value * investment.bond_isin.interest_rate))
            else:
                future_portfolio_balance += investment.volume * investment.bond_isin.value

        data = {
            'average_interest_rate': average_interest_rate,
            'soon_expires': {
                'bond_name': soon_expires.bond_isin.name,
                'bond_isin': soon_expires.bond_isin.isin,
                'bond_expiration_date': soon_expires.bond_isin.expiration_date,
            },
            'portfolio_balance': portfolio_balance,
            'future_portfolio_balance': future_portfolio_balance,
        }
        return Response(data, status=status.HTTP_200_OK)


class PurchaseBondView(APIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = InvestmentSerializer

    def post(self, request):
        data = request.data
        username = data.get('username')
        bond_isin = data.get('bond_isin')
        volume = int(data.get('volume'))

        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)

        try:
            Bond.objects.get(isin=bond_isin)
        except Bond.DoesNotExist:
            return Response({'error': 'Bond not found'}, status=404)

        if volume <= 0:
            return Response({'error': 'Invalid volume'}, status=400)

        investment_data = {
            'username': username,
            'bond_isin': bond_isin,
            'volume': volume,
        }

        serializer = InvestmentSerializer(data=investment_data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class UserPortfolioBondListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = BondSerializer

    def get_queryset(self):
        investment_query_set = Investment.objects.filter(username=self.kwargs['username'])
        return Bond.objects.filter(isin__in=investment_query_set.values('bond_isin'))


class UserPortfolioInvestmentListView(ListAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = Bond.objects.all()
    serializer_class = InvestmentSerializer

    def get_queryset(self):
        return Investment.objects.filter(username=self.kwargs['username'])


class AuthenticationView(APIView):
    serializer_class = UserSerializer

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        if not username or not password:
            return Response(
                {
                    'username, password': [
                        'This fields are required.'
                    ]
                },
                status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(username=username, password=password)
        if not user:
            try:
                User.objects.create_user(username=username, password=password)
                user = authenticate(username=username, password=password)
            except:
                return Response(
                    {
                        'detail': [
                            'Invalid Credentials'
                        ]
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                'token': token.key
            },
            status=status.HTTP_200_OK
        )
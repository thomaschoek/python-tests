import inspect
from hypothesis import given, strategies as strats
from typing import get_origin, get_args

import pytest


class AutoTestBase:
    """Base class that automatically generates and runs tests for the methods of a given class."""
    class_to_test = None
    
    def _generate_strategy(self, param: inspect.Parameter):
        """Generate a Hypothesis strategy for a given type annotation."""
        if param.default and param.default != inspect.Parameter.empty:
            return strats.just(param.default)

        param_type = param.annotation
        param_origin = get_origin(param_type)
        param_args = get_args(param_type)

        # Handle nested types
        if param_origin is list and param_args:
            return strats.lists(self._generate_strategy(param_args[0]))
        elif param_origin is dict and param_args:
            return strats.dictionaries(self._generate_strategy(param_args[0]), self._generate_strategy(param_args[1]))
        else:
            try:
                return strats.from_type(param.annotation)
            except BaseException as exc:
                print(f'Failed to generate strategy for {param}: {exc}')
                return strats.none()
     
    async def _auto_test_method(self, method):
        """Automatically test a method using type hints."""
        signature = inspect.signature(method)
        parameters = signature.parameters
        return_type = signature.return_annotation

        if not return_type or return_type is None or return_type is inspect.Signature.empty:
            return_type = type(None)

        # Generate Hypothesis strategies for each parameter
        strategies = [self._generate_strategy(param) for param in parameters.values()]

        @given(strats.data())
        def test_case(data):
            # Convert the generated data to the correct types
            if inspect.iscoroutinefunction(method):
                return
            args = []
            for strat in strategies:
                try:
                    args.append(data.draw(strat))
                except BaseException as exc:
                    print(f'Failed to draw {strat}: {exc}')
                    args.append(None)
                #result = asyncio.run(method(*args))
            result = method(*args)
            if return_type and return_type is not inspect.Signature.empty:
                assert isinstance(result, return_type), f"Expected {return_type}, got {type(result)}"

        # @given lets hypothesis pass in params
        test_case()

    def _get_public_methods(self, cls):
        return filter(lambda info: not info[0].startswith('_'), inspect.getmembers(cls, predicate=inspect.ismethod))

    @pytest.mark.asyncio
    async def test_public_methods_property_based(self):
        """Run tests for all methods with type annotations."""
        for _, method in self._get_public_methods(self.class_to_test):
            await self._auto_test_method(method)

